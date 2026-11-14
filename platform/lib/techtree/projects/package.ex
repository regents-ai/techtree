defmodule Techtree.Projects.Package do
  @moduledoc """
  A project's package as the team uploads it: one gzipped tar the factory made,
  holding `manifest.json` (`Techtree.Projects.Manifest`), `report.md`, the
  original and selected Skill, the final test's cases and how to run it again.

  It is opened in memory and refused, with nothing kept, unless all of this
  holds: at most 5 MB as uploaded and 25 MB unpacked; one gzip stream with
  nothing after it; at most 2,000 entries, each a plain file or a folder on a
  path inside the package (never from the root of a disk, never through
  `..`), so no links or devices; no file twice; a manifest that passes its
  checks; exactly the files the manifest lists, each with its size and
  sha256; and a `report.md` of UTF-8 text, at most 1 MB.
  """

  alias Techtree.Projects.Manifest

  @max_bytes 5_242_880
  @max_unpacked 26_214_400
  @max_entries 2_000
  @max_report 1_048_576

  @type t :: %{manifest: map(), report: String.t(), sha256: String.t(), size: pos_integer()}

  @doc "The most an uploaded package may be, in bytes."
  @spec max_bytes() :: pos_integer()
  def max_bytes, do: @max_bytes

  @doc "What the package holds that a project keeps, or what is wrong with it."
  @spec read(binary()) :: {:ok, t()} | {:error, String.t()}
  def read(bytes) when byte_size(bytes) > @max_bytes, do: {:error, "The package is over 5 MB."}

  def read(bytes) do
    with {:ok, tar} <- gunzip(bytes),
         {:ok, paths} <- paths(tar),
         {:ok, files} <- files(tar, paths),
         {:ok, json} <- fetch(files, "manifest.json"),
         {:ok, manifest} <- Manifest.parse(json),
         :ok <- listed(manifest["files"], Map.delete(files, "manifest.json")),
         {:ok, report} <- report(files["report.md"]) do
      {:ok, %{manifest: manifest, report: report, sha256: sha256(bytes), size: byte_size(bytes)}}
    end
  end

  @doc "The sha256 of `bytes`, in lowercase hex."
  @spec sha256(binary()) :: String.t()
  def sha256(bytes), do: :sha256 |> :crypto.hash(bytes) |> Base.encode16(case: :lower)

  defp gunzip(bytes) do
    z = :zlib.open()

    try do
      # 31: a gzip stream, with zlib's largest window.
      :ok = :zlib.inflateInit(z, 31)

      with {:ok, tar} <- inflate(z, :zlib.safeInflate(z, bytes), [], 0),
           :ok <- ends_with(bytes, tar) do
        {:ok, tar}
      end
    rescue
      ErlangError -> {:error, "The package isn't a gzipped file, or it is cut short."}
    after
      :zlib.close(z)
    end
  end

  # Inflates a piece at a time, stopping as soon as the output passes the limit.
  defp inflate(z, {state, out}, pieces, size) do
    size = size + IO.iodata_length(out)

    cond do
      size > @max_unpacked ->
        {:error, "The package unpacks to more than 25 MB."}

      # Checks the stream's own length and checksum: a cut-short package also
      # stops at its end, and raises here.
      state == :finished ->
        :ok = :zlib.inflateEnd(z)
        {:ok, IO.iodata_to_binary(Enum.reverse([out | pieces]))}

      true ->
        inflate(z, :zlib.safeInflate(z, []), [out | pieces], size)
    end
  end

  # zlib stops at the end of the first gzip stream and ignores what follows.
  # A gzip stream ends with its unpacked bytes' CRC-32 and length, so a file
  # whose last eight bytes are not those has more after the stream.
  defp ends_with(bytes, tar) do
    crc = :erlang.crc32(tar)
    length = rem(byte_size(tar), 4_294_967_296)

    case binary_part(bytes, byte_size(bytes), -8) do
      <<^crc::little-32, ^length::little-32>> -> :ok
      _more -> {:error, "The package has more after the end of its gzip stream."}
    end
  end

  # The paths of the tar's files, once each, after checking every entry.
  defp paths(tar) do
    case :erl_tar.table({:binary, tar}, [:verbose]) do
      {:ok, entries} when length(entries) > @max_entries ->
        {:error, "The package holds more than 2,000 entries."}

      {:ok, entries} ->
        Enum.reduce_while(entries, {:ok, MapSet.new()}, &entry/2)

      {:error, _reason} ->
        {:error, "The package isn't a tar file."}
    end
  end

  defp entry({name, type, _size, _mtime, _mode, _uid, _gid}, {:ok, paths}) do
    path = path(name)

    cond do
      not is_binary(path) ->
        {:halt, {:error, "The package holds a name that isn't UTF-8."}}

      String.starts_with?(path, "/") ->
        {:halt, {:error, "The package holds #{path}, a path from the root of a disk."}}

      ".." in String.split(path, "/") ->
        {:halt, {:error, "The package holds #{path}, a path that leaves the package."}}

      type == :directory ->
        {:cont, {:ok, paths}}

      type in [:symlink, :hard_link] ->
        {:halt, {:error, "The package holds a link, #{path}. Only files are allowed."}}

      type != :regular ->
        {:halt, {:error, "The package holds #{path}, which isn't a file."}}

      MapSet.member?(paths, path) ->
        {:halt, {:error, "The package holds #{path} twice."}}

      true ->
        {:cont, {:ok, MapSet.put(paths, path)}}
    end
  end

  # A tar made from inside a folder (`tar -C folder .`) names each file from
  # `./`, and a folder entry may end in `/`.
  defp path(name) do
    case :unicode.characters_to_binary(name) do
      path when is_binary(path) ->
        path |> String.replace_prefix("./", "") |> String.trim_trailing("/")

      _not_utf8 ->
        nil
    end
  end

  defp files(tar, paths) do
    case :erl_tar.extract({:binary, tar}, [:memory]) do
      {:ok, files} ->
        files = Map.new(files, fn {name, bytes} -> {path(name), bytes} end)
        if MapSet.equal?(MapSet.new(Map.keys(files)), paths), do: {:ok, files}, else: unreadable()

      {:error, _reason} ->
        unreadable()
    end
  end

  defp unreadable, do: {:error, "The package's files couldn't be read."}

  defp fetch(files, path) do
    case Map.fetch(files, path) do
      {:ok, bytes} -> {:ok, bytes}
      :error -> {:error, "The package has no #{path}."}
    end
  end

  # Exactly the files the manifest lists, each the size and sha256 it gives.
  defp listed(listed, files) do
    by_path = Map.new(listed, &{&1["path"], &1})

    cond do
      unlisted = files |> Map.keys() |> Enum.sort() |> Enum.find(&(not Map.has_key?(by_path, &1))) ->
        {:error, "The package holds #{unlisted}, which manifest.json doesn't list."}

      missing = Enum.find(listed, &(not Map.has_key?(files, &1["path"]))) ->
        {:error, "manifest.json lists #{missing["path"]}, which the package doesn't hold."}

      other = Enum.find(listed, &(byte_size(files[&1["path"]]) != &1["size_bytes"])) ->
        {:error, "#{other["path"]} isn't the size manifest.json gives."}

      other = Enum.find(listed, &(sha256(files[&1["path"]]) != &1["sha256"])) ->
        {:error, "#{other["path"]} doesn't match its sha256 in manifest.json."}

      true ->
        :ok
    end
  end

  defp report(bytes) when byte_size(bytes) > @max_report, do: {:error, "report.md is over 1 MB."}

  defp report(bytes) do
    if String.valid?(bytes), do: {:ok, bytes}, else: {:error, "report.md isn't UTF-8 text."}
  end
end
