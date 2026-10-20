defmodule Techtree.WalletBench.TurnArchive do
  @moduledoc """
  A turn's folder as the machine sends it back: a gzipped tar, base64 encoded.

  The machine refuses to pack a folder over 20 MB, but the tested agent controls
  the machine, so the app does not trust that check: it unpacks the archive only
  while what comes out stays within the folder limit (plus room for the tar's
  own headers), however small the archive was. Every file keeps a name that is
  safe to unpack anywhere (`Techtree.WalletBench.Evidence.file_name?/1`), and no
  two files share one; an archive that breaks either is not kept.
  """

  alias Techtree.WalletBench.Evidence

  @max_folder_bytes 20_000_000
  # Each file in a tar adds a 512-byte header and pads its bytes to 512.
  @max_tar_bytes @max_folder_bytes + 1_000_000
  # gzip can grow incompressible bytes a little, then base64 adds a third.
  @max_encoded_bytes div(@max_folder_bytes * 4, 3) + 1_000_000

  @doc "The most a turn's folder may hold, in bytes."
  @spec max_folder_bytes() :: pos_integer()
  def max_folder_bytes, do: @max_folder_bytes

  @doc "The files in an encoded archive, by name."
  @spec unpack(binary()) :: {:ok, %{String.t() => binary()}} | {:error, String.t()}
  def unpack(encoded) when byte_size(encoded) > @max_encoded_bytes,
    do: {:error, "The turn's archive is #{byte_size(encoded)} bytes, over its limit."}

  def unpack(encoded) do
    with {:ok, compressed} <- decode(encoded),
         {:ok, tar} <- gunzip(compressed),
         {:ok, entries} <- :erl_tar.extract({:binary, tar}, [:memory]),
         files =
           Enum.map(entries, fn {name, content} ->
             {name |> to_string() |> Path.basename(), content}
           end),
         :ok <- names_kept(Enum.map(files, &elem(&1, 0))) do
      {:ok, Map.new(files)}
    else
      {:error, reason} when is_binary(reason) -> {:error, reason}
      {:error, reason} -> {:error, "The turn's archive did not unpack: #{inspect(reason)}"}
    end
  end

  defp decode(encoded) do
    case Base.decode64(encoded) do
      {:ok, compressed} -> {:ok, compressed}
      :error -> {:error, "The turn's archive did not decode."}
    end
  end

  # Inflates a piece at a time, stopping as soon as the output passes the limit.
  defp gunzip(compressed) do
    z = :zlib.open()

    try do
      # 31: a gzip stream, with zlib's largest window.
      :ok = :zlib.inflateInit(z, 31)
      inflate(z, :zlib.safeInflate(z, compressed), [], 0)
    rescue
      error in ErlangError ->
        {:error, "The turn's archive did not unpack: #{inspect(error.original)}"}
    after
      :zlib.close(z)
    end
  end

  defp inflate(z, {state, out}, pieces, size) do
    size = size + IO.iodata_length(out)

    cond do
      size > @max_tar_bytes ->
        {:error,
         "The turn's archive unpacks to more than #{div(@max_tar_bytes, 1_000_000)} MB, over its limit."}

      state == :finished ->
        {:ok, IO.iodata_to_binary(Enum.reverse([out | pieces]))}

      true ->
        inflate(z, :zlib.safeInflate(z, []), [out | pieces], size)
    end
  end

  defp names_kept(names) do
    cond do
      unsafe = Enum.find(names, &(not Evidence.file_name?(&1))) ->
        {:error, "The turn's archive holds a file whose name can't be kept: #{inspect(unsafe)}."}

      length(Enum.uniq(names)) != length(names) ->
        {:error, "The turn's archive holds two files with the same name."}

      true ->
        :ok
    end
  end
end
