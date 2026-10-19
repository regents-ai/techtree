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

  @doc """
  Whether a file a turn recorded may keep its name: 1 to 128 characters, not
  `.` or `..`, with no slash, backslash, control character or any of
  `: * ? " < > |`. A name like that is the same single file on every system a
  download is unpacked on, and reaches nothing outside its folder.
  """
  @spec file_name?(String.t()) :: boolean()
  def file_name?(name),
    do: name not in [".", ".."] and name =~ ~r/\A[^\/\\\x00-\x1f\x7f:*?"<>|]{1,128}\z/u

  @doc """
  Reads a recorded file through without keeping it, and says whether its size
  and sha256 still match what the turn recorded.
  """
  @spec check(struct(), String.t()) :: :ok | {:error, term()}
  def check(%{attempt_id: attempt_id, test: test, evidence: evidence}, file) do
    turn = Catalog.turn_name(test)

    with %{"bytes" => bytes, "sha256" => sha256} <-
           Map.get(evidence || %{}, file, {:error, "#{turn} recorded no #{file}."}),
         {:ok, {^bytes, digest}} <- digest(turn_key(attempt_id, turn, file)) do
      if Base.encode16(digest, case: :lower) == sha256,
        do: :ok,
        else:
          {:error, "The stored #{file} of #{turn} does not match the sha256 recorded with it."}
    else
      {:ok, {_other_size, _digest}} ->
        {:error, "The stored #{file} of #{turn} is not the size recorded with it."}

      {:error, reason} ->
        {:error, reason}
    end
  end

  # The size and sha256 of what is stored under `key`, read as it arrives.
  defp digest(key) do
    into = fn {:data, data}, {request, response} ->
      {size, hash} = Req.Response.get_private(response, :digest, {0, :crypto.hash_init(:sha256)})
      digest = {size + byte_size(data), :crypto.hash_update(hash, data)}
      {:cont, {request, Req.Response.put_private(response, :digest, digest)}}
    end

    case Req.get(request(key), into: into) do
      {:ok, %Req.Response{status: 200} = response} ->
        {size, hash} =
          Req.Response.get_private(response, :digest, {0, :crypto.hash_init(:sha256)})

        {:ok, {size, :crypto.hash_final(hash)}}

      {:ok, %Req.Response{status: status}} ->
        {:error, {:evidence, status}}

      {:error, exception} ->
        {:error, exception}
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
