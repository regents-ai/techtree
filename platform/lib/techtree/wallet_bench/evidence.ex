defmodule Techtree.WalletBench.Evidence do
  @moduledoc """
  The bench's evidence bucket: transcripts, machine output and reports, stored
  by key in a private Tigris bucket and read back by key.

  Requests are signed with Req's AWS signature step. `config/runtime.exs` sets
  the endpoint, bucket, region and keys from the `WALLETBENCH_AWS_*` and
  `WALLETBENCH_BUCKET_NAME` environment variables; tests add Req options, such as
  a `Req.Test` plug, under `:req_options`.
  """

  alias Techtree.WalletBench.Catalog

  @doc "Where one file of an attempt's turn is stored."
  @spec turn_key(Ecto.UUID.t(), String.t(), String.t()) :: String.t()
  def turn_key(attempt_id, turn_name, file), do: "attempts/#{attempt_id}/#{turn_name}/#{file}"

  @doc "Stores `body` under `key`, replacing anything there."
  @spec put(String.t(), iodata(), String.t()) :: :ok | {:error, term()}
  def put(key, body, content_type) do
    case Req.put(request(key), body: body, headers: [content_type: content_type]) do
      {:ok, %Req.Response{status: 200}} -> :ok
      {:ok, %Req.Response{status: status}} -> {:error, {:evidence, status}}
      {:error, exception} -> {:error, exception}
    end
  end

  @doc """
  One file a turn recorded, read back only when its bytes still match the
  sha256 recorded with them on the turn. Every reader of a turn's files, the
  judge and the public evidence page, reads through here.
  """
  @spec recorded(struct(), String.t()) :: {:ok, binary()} | {:error, term()}
  def recorded(%{attempt_id: attempt_id, test: test, evidence: evidence}, file) do
    turn = Catalog.turn_name(test)

    with {:ok, sha256} <- fingerprint(evidence, turn, file),
         {:ok, body} <- get(turn_key(attempt_id, turn, file)) do
      if Base.encode16(:crypto.hash(:sha256, body), case: :lower) == sha256,
        do: {:ok, body},
        else:
          {:error, "The stored #{file} of #{turn} does not match the sha256 recorded with it."}
    end
  end

  defp fingerprint(evidence, turn, file) do
    case evidence do
      %{^file => %{"sha256" => sha256}} -> {:ok, sha256}
      _no_record -> {:error, "#{turn} recorded no #{file}."}
    end
  end

  @doc "Reads what is stored under `key`."
  @spec get(String.t()) :: {:ok, binary()} | {:error, term()}
  def get(key) do
    case Req.get(request(key)) do
      {:ok, %Req.Response{status: 200, body: body}} -> {:ok, body}
      {:ok, %Req.Response{status: status}} -> {:error, {:evidence, status}}
      {:error, exception} -> {:error, exception}
    end
  end

  defp request(key) do
    config = Application.fetch_env!(:techtree, __MODULE__)

    Req.new(
      [
        base_url: Keyword.fetch!(config, :endpoint),
        url: "/" <> Keyword.fetch!(config, :bucket) <> "/" <> encode_key(key),
        decode_body: false,
        retry: false,
        aws_sigv4: [
          service: :s3,
          region: Keyword.fetch!(config, :region),
          access_key_id: Keyword.fetch!(config, :access_key_id),
          secret_access_key: Keyword.fetch!(config, :secret_access_key)
        ]
      ] ++ Keyword.get(config, :req_options, [])
    )
  end

  defp encode_key(key) do
    key
    |> String.split("/")
    |> Enum.map_join("/", fn segment -> URI.encode(segment, &URI.char_unreserved?/1) end)
  end
end
