defmodule Techtree.Watchdog.Ownership do
  @moduledoc """
  Proves a customer owns a host, the one and only request Watchdog ever makes
  about a customer's site in this slice.

  A host is proven in one of two ways, the person's choice when they add it:

    * `:dns_txt` — they publish a TXT record on the host whose value is the
      host's record string (`txt_value/1`). We read it through a public
      DNS-over-HTTPS resolver (`dns.google`), so this method never touches the
      customer's site at all.
    * `:well_known_file` — they publish a file at `/.well-known/techtree-watchdog.txt`
      (`well_known_path/0`) whose contents are that same string. We fetch it over
      HTTPS. This is the single request Watchdog sends to a customer host.

  Before any well-known fetch the host is resolved once and held to
  `public_host?/1`: a loopback, link-local, private, unique-local or otherwise
  non-public address is refused and nothing is sent. The fetch then connects to
  one of the addresses just checked, never resolving the name again, and keeps
  the host's name for the `Host` header, TLS SNI and certificate verification,
  so a name that changes its answer between the check and the connection
  cannot point the request inward. The fetch is one request on its own
  connection (`Techtree.Watchdog.Ownership.SingleRequest`), closed afterwards.
  It follows no redirects, retries nothing, gives up quickly and reads only a
  small, bounded amount, so a customer host cannot use the check to reach
  anything else or to hand back an unbounded body.

  `verify/1` tells a missing proof apart from a check that could not be made:
  only `{:error, :proof_missing}` says the proof is positively not there (the
  TXT record is absent or different, or the file is missing or different).
  Every other error means the proof could not be read this time.

  Every request is a `Req` request built with `request_options/0`, so tests
  drive both methods with `Req.Test` and the real resolver and site are never
  reached. The file fetch's adapter is `SingleRequest` unless `:file_adapter`
  is configured, as the test configuration does to stay on this machine.
  """

  alias Techtree.Watchdog.Ownership.SingleRequest

  @resolver "https://dns.google/resolve"
  @well_known_path "/.well-known/techtree-watchdog.txt"
  @record_prefix "techtree-watchdog-verification="
  @timeout 5_000
  @max_answers 50

  @doc "The path a well-known proof file is published at."
  @spec well_known_path() :: String.t()
  def well_known_path, do: @well_known_path

  @doc "A fresh random token for a host's proof, the secret part of its record string."
  @spec new_token() :: String.t()
  def new_token, do: Base.url_encode64(:crypto.strong_rand_bytes(24), padding: false)

  @doc "The exact string a host publishes to prove ownership, in its TXT record or its file."
  @spec record_value(%{verification_token: String.t()}) :: String.t()
  def record_value(%{verification_token: token}), do: @record_prefix <> token

  @doc "The name of the TXT record a host publishes (the host itself)."
  @spec txt_name(%{origin: String.t()}) :: String.t()
  def txt_name(%{origin: origin}), do: origin

  @doc "The full URL a well-known proof file is read from."
  @spec well_known_url(%{origin: String.t()}) :: String.t()
  def well_known_url(%{origin: origin}), do: "https://" <> origin <> @well_known_path

  @doc """
  Checks a host's published proof: `:ok` when it is there and matches,
  `{:error, :proof_missing}` when the record or file is absent or says something
  else, or `{:error, reason}` when the proof could not be read (the resolver or
  the host could not be reached or answered with an error, or the host is not
  public).
  """
  @spec verify(%{
          :ownership_method => :dns_txt | :well_known_file,
          :origin => String.t(),
          :verification_token => String.t(),
          optional(any()) => any()
        }) :: :ok | {:error, :proof_missing | term()}
  def verify(%{ownership_method: :dns_txt} = host), do: verify_dns(host)
  def verify(%{ownership_method: :well_known_file} = host), do: verify_well_known(host)

  defp verify_dns(host) do
    options =
      [url: @resolver, params: [name: txt_name(host), type: "TXT"]]
      |> Keyword.merge(request_options())

    request([]) |> Req.get(options) |> dns_result(record_value(host))
  end

  defp dns_result({:ok, %{status: 200, body: body}}, expected),
    do: body |> decode() |> dns_answer(expected)

  defp dns_result({:ok, %{status: status}}, _expected), do: {:error, {:resolver_status, status}}
  defp dns_result({:error, _exception}, _expected), do: {:error, :resolver_unreachable}

  # The resolver's own status: 0 is an answer and 3 is a name that does not
  # exist, both a real finding; anything else (a failed lookup) is not.
  defp dns_answer(%{"Status" => status} = answer, expected) when status in [0, 3],
    do: if(expected in txt_answers(answer), do: :ok, else: {:error, :proof_missing})

  defp dns_answer(_answer, _expected), do: {:error, :resolver_failed}

  defp verify_well_known(host) do
    with {:ok, address} <- guard_public(host) do
      options = Keyword.merge([url: address_url(address)], request_options())

      request(hostname: host.origin)
      |> Req.merge(adapter: file_adapter())
      |> Req.get(options)
      |> file_result(record_value(host))
    end
  end

  # The well-known URL with the checked address in place of the name.
  defp address_url(address) do
    host = to_string(:inet.ntoa(address))
    URI.to_string(%URI{scheme: "https", host: host, path: @well_known_path})
  end

  defp file_result({:ok, %{status: 200, body: body}}, expected),
    do: if(String.trim(to_string(body)) == expected, do: :ok, else: {:error, :proof_missing})

  defp file_result({:ok, %{status: 404}}, _expected), do: {:error, :proof_missing}
  defp file_result({:ok, %{status: status}}, _expected), do: {:error, {:file_status, status}}
  defp file_result({:error, _exception}, _expected), do: {:error, :host_unreachable}

  defp decode(body) when is_map(body), do: body
  defp decode(body) when is_binary(body), do: Jason.decode(body) |> ok_or_empty()
  defp decode(_body), do: %{}

  defp ok_or_empty({:ok, decoded}), do: decoded
  defp ok_or_empty(_error), do: %{}

  # A JSON DNS answer lists each record under "Answer"; a TXT value arrives
  # wrapped in quotes and may be split into several quoted strings, which join.
  defp txt_answers(%{"Answer" => answers}) when is_list(answers) do
    answers
    |> Enum.take(@max_answers)
    |> Enum.filter(&(Map.get(&1, "type") == 16))
    |> Enum.map(&unquote_txt(Map.get(&1, "data", "")))
  end

  defp txt_answers(_body), do: []

  defp unquote_txt(data) do
    ~r/"([^"]*)"/
    |> Regex.scan(data)
    |> Enum.map_join("", fn [_whole, inner] -> inner end)
    |> case do
      "" -> String.trim(data, "\"")
      joined -> joined
    end
  end

  @doc """
  Whether a host names a public Internet address Watchdog may fetch from:
  not a loopback, link-local, private, unique-local, multicast or otherwise
  reserved address, and not a local-only name. A name is resolved and every
  address it resolves to must be public.
  """
  @spec public_host?(%{origin: String.t()} | String.t()) :: boolean()
  def public_host?(%{origin: origin}), do: public_host?(origin)

  def public_host?(origin) when is_binary(origin) do
    match?({:ok, _address}, guard_public(%{origin: origin}))
  end

  defp guard_public(%{origin: origin}) do
    cond do
      origin in ["", "localhost"] -> {:error, :host_not_public}
      local_name?(origin) -> {:error, :host_not_public}
      true -> guard_addresses(origin)
    end
  end

  defp local_name?(origin) do
    String.ends_with?(origin, [".localhost", ".local", ".internal", ".home.arpa"])
  end

  # An address literal is judged directly; a name is resolved and every address
  # it maps to over IPv4 and IPv6 must be public, so a name that points inward
  # is refused before any request is built. The first checked address is the
  # one the fetch connects to.
  defp guard_addresses(origin) do
    case :inet.parse_address(String.to_charlist(origin)) do
      {:ok, address} -> judge([address])
      {:error, _not_an_address} -> judge(resolver().(origin))
    end
  end

  defp judge([]), do: {:error, :host_unresolved}

  defp judge([first | _rest] = addresses) do
    if Enum.all?(addresses, &public_address?/1),
      do: {:ok, first},
      else: {:error, :host_not_public}
  end

  defp resolver do
    Application.get_env(:techtree, __MODULE__, [])[:resolver] || (&default_resolve/1)
  end

  defp default_resolve(origin) do
    charlist = String.to_charlist(origin)
    Enum.flat_map([:inet, :inet6], &resolve(charlist, &1))
  end

  defp resolve(charlist, family) do
    case :inet.getaddrs(charlist, family, @timeout) do
      {:ok, addresses} -> addresses
      {:error, _reason} -> []
    end
  end

  # IPv4: reject this-host, private, loopback, link-local, shared, documentation,
  # benchmarking and reserved ranges. IPv6: reject loopback, unspecified,
  # unique-local, link-local, multicast and IPv4-mapped inward addresses.
  defp public_address?({a, b, c, d}), do: not private_v4?(a, b, c, d)
  defp public_address?({0, 0, 0, 0, 0, 0, 0, 0}), do: false
  defp public_address?({0, 0, 0, 0, 0, 0, 0, 1}), do: false
  defp public_address?({0, 0, 0, 0, 0, 65_535, a, b}), do: public_address?(mapped(a, b))
  defp public_address?({first, _, _, _, _, _, _, _}) when first in 0xFE80..0xFEBF, do: false
  defp public_address?({first, _, _, _, _, _, _, _}) when first in 0xFC00..0xFDFF, do: false
  defp public_address?({first, _, _, _, _, _, _, _}) when first in 0xFF00..0xFFFF, do: false
  defp public_address?({_, _, _, _, _, _, _, _}), do: true

  defp private_v4?(a, _b, _c, _d) when a in [0, 10, 127], do: true
  defp private_v4?(172, b, _c, _d) when b in 16..31, do: true
  defp private_v4?(192, 168, _c, _d), do: true
  defp private_v4?(169, 254, _c, _d), do: true
  defp private_v4?(100, b, _c, _d) when b in 64..127, do: true
  defp private_v4?(192, 0, _c, _d), do: true
  defp private_v4?(a, _b, _c, _d) when a in 224..255, do: true
  defp private_v4?(_a, _b, _c, _d), do: false

  defp mapped(a, b),
    do: {Bitwise.bsr(a, 8), Bitwise.band(a, 0xFF), Bitwise.bsr(b, 8), Bitwise.band(b, 0xFF)}

  defp request(connect_options) do
    Req.new(
      redirect: false,
      retry: false,
      receive_timeout: @timeout,
      connect_options: [timeout: @timeout] ++ connect_options,
      decode_body: false
    )
  end

  defp file_adapter,
    do: Application.get_env(:techtree, __MODULE__, [])[:file_adapter] || SingleRequest

  @doc "Req options tests override to answer both methods without a network."
  @spec request_options() :: keyword()
  def request_options,
    do: Application.get_env(:techtree, __MODULE__, [])[:req_options] || []
end
