defmodule Techtree.Catalog.DigestTest do
  use ExUnit.Case, async: true

  alias Techtree.Catalog.Digest

  doctest Techtree.Catalog.Digest

  describe "valid?/1" do
    test "accepts exactly sha256 and 64 lowercase hexadecimal characters" do
      assert Digest.valid?("sha256:" <> String.duplicate("a", 64))
      assert Digest.valid?("sha256:" <> String.duplicate("0", 64))
    end

    test "rejects uppercase, the wrong length, and the wrong algorithm" do
      refute Digest.valid?("sha256:" <> String.duplicate("A", 64))
      refute Digest.valid?("sha256:" <> String.duplicate("a", 63))
      refute Digest.valid?("sha256:" <> String.duplicate("a", 65))
      refute Digest.valid?("sha512:" <> String.duplicate("a", 64))
      refute Digest.valid?(String.duplicate("a", 64))
      refute Digest.valid?(nil)
    end
  end

  describe "hash_bytes/1" do
    test "addresses bytes, not documents" do
      compact = ~s({"a":1})
      spaced = ~s({"a": 1})

      refute Digest.hash_bytes(compact) == Digest.hash_bytes(spaced)
    end
  end

  describe "verify_bytes/2" do
    test "accepts the bytes it was computed from" do
      bytes = "the exact bytes"

      assert :ok == Digest.verify_bytes(bytes, Digest.hash_bytes(bytes))
    end

    test "reports the computed digest when the bytes drifted" do
      digest = Digest.hash_bytes("the exact bytes")

      assert {:error, computed} = Digest.verify_bytes("the exact byte", digest)
      assert computed == Digest.hash_bytes("the exact byte")
    end

    test "refuses an uppercase spelling of the right digest" do
      bytes = "the exact bytes"
      shouted = String.upcase(Digest.hash_bytes(bytes))

      assert {:error, _computed} = Digest.verify_bytes(bytes, shouted)
    end
  end

  describe "parse!/1" do
    test "returns the 32 raw bytes a digest names" do
      assert byte_size(Digest.parse!(Digest.hash_bytes(""))) == 32
    end

    test "raises on anything that is not a digest" do
      assert_raise ArgumentError, fn -> Digest.parse!("sha256:nope") end
    end
  end
end
