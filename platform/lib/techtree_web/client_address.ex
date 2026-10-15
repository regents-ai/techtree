defmodule TechtreeWeb.ClientAddress do
  @moduledoc """
  The address a request's rate limits are keyed by.

  Production runs only behind Fly's proxy, which terminates the connection, so
  the peer is the proxy and the client address arrives in the one header the
  proxy sets itself, replacing any value a client sent. Anywhere else nothing
  replaces that header, so the direct peer decides and no request header is
  read. `X-Forwarded-For` is never read: a client writes its first entries.
  """

  @behind_fly_proxy Application.compile_env!(:techtree, :behind_fly_proxy)

  @doc """
  The limiter key for `conn` and where it came from.

  Behind Fly, anything but exactly one parseable `Fly-Client-IP` keys the
  proxy-wide peer bucket rather than a second header a client could forge
  itself a private budget with.
  """
  @spec key(Plug.Conn.t()) :: {:inet.ip_address(), :client_header | :peer | :peer_fallback}
  def key(conn) do
    if @behind_fly_proxy, do: fly_client(conn), else: {normalized(conn.remote_ip), :peer}
  end

  @doc """
  The key a request's address spends its post and search allowances under: the
  limiter key, keyed-hashed, so it can travel in a signed page token without
  naming the address. A page keeps the key of the request that rendered it.
  """
  @spec client_key(Plug.Conn.t()) :: String.t()
  def client_key(conn) do
    {address, _source} = key(conn)
    secret = TechtreeWeb.Endpoint.config(:secret_key_base)

    :hmac
    |> :crypto.mac(:sha256, secret, :erlang.term_to_binary(address))
    |> binary_part(0, 16)
    |> Base.url_encode64(padding: false)
  end

  defp fly_client(conn) do
    with [value] <- Plug.Conn.get_req_header(conn, "fly-client-ip"),
         {:ok, address} <- value |> :binary.bin_to_list() |> :inet.parse_strict_address() do
      {normalized(address), :client_header}
    else
      _absent_duplicated_or_unparseable -> {normalized(conn.remote_ip), :peer_fallback}
    end
  end

  # The mapped and compatible IPv6 spellings of one IPv4 address share its
  # bucket, and a genuine IPv6 client is keyed by its /64 so one host cannot
  # spend the budget once per address in the block it was handed. The key is
  # never persisted, rendered or logged; it lives only in the limiter.
  defp normalized({_, _, _, _} = ipv4), do: ipv4

  defp normalized({0, 0, 0, 0, 0, embedding, high, low}) when embedding in [0, 0xFFFF] do
    <<a, b, c, d>> = <<high::16, low::16>>
    {a, b, c, d}
  end

  defp normalized({a, b, c, d, _, _, _, _}), do: {a, b, c, d, 0, 0, 0, 0}
end
