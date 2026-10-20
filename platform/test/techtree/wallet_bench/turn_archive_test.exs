defmodule Techtree.WalletBench.TurnArchiveTest do
  # The tested agent controls the machine that packs its turn's folder, so the
  # app checks what the archive unpacks to itself (security assessment of
  # 19 Oct, finding 4).
  use ExUnit.Case, async: true

  alias Techtree.WalletBench.TurnArchive

  defp archive(files) do
    entries = Enum.map(files, fn {name, content} -> {String.to_charlist(name), content} end)
    path = Path.join(System.tmp_dir!(), "turn-#{System.unique_integer([:positive])}.tar.gz")
    :ok = :erl_tar.create(String.to_charlist(path), entries, [:compressed])
    encoded = path |> File.read!() |> Base.encode64()
    File.rm!(path)
    encoded
  end

  test "a turn's files come back by name, byte for byte" do
    files = %{"session.jsonl" => ~s({"a": 1}\n), "exit_code" => "0\n"}
    assert TurnArchive.unpack(archive(files)) == {:ok, files}
  end

  test "a small archive that unpacks past the folder limit is refused" do
    encoded = archive(%{"session.jsonl" => :binary.copy(<<0>>, 64_000_000)})
    assert byte_size(encoded) < 1_000_000

    assert {:error, "The turn's archive unpacks to more than 21 MB, over its limit."} =
             TurnArchive.unpack(encoded)
  end

  test "an archive at the folder limit is kept" do
    content = :binary.copy(<<1>>, TurnArchive.max_folder_bytes())

    assert {:ok, %{"session.jsonl" => ^content}} =
             TurnArchive.unpack(archive(%{"session.jsonl" => content}))
  end

  test "an archive that is not gzip, or not base64, is refused" do
    assert {:error, "The turn's archive did not unpack: " <> _} =
             TurnArchive.unpack(Base.encode64("not gzip"))

    assert {:error, "The turn's archive did not decode."} = TurnArchive.unpack("%%%")
  end

  test "a file whose name could reach outside its folder is refused" do
    assert {:error, "The turn's archive holds a file whose name can't be kept: " <> _} =
             TurnArchive.unpack(archive(%{"what?" => "x"}))
  end
end
