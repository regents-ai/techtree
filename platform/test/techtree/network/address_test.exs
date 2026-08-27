defmodule Techtree.Network.AddressTest do
  @moduledoc """
  The checksum has to actually catch a wrong character, and the hash under it
  has to actually be Keccak.

  Both are checked against published vectors rather than against this
  repository's own output: the eight addresses EIP-55 prints as its examples,
  and Keccak-256 digests taken from a reference implementation, including
  messages either side of the 136-byte block boundary so the padding is
  exercised rather than assumed.
  """

  use ExUnit.Case, async: true

  alias Techtree.Network.Address
  alias Techtree.Network.Keccak

  doctest Techtree.Network.Address

  # The examples printed in EIP-55.
  @checksummed [
    "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed",
    "0xfB6916095ca1df60bB79Ce92cE3Ea74c37c5d359",
    "0xdbF03B407c01E7cD3CBea99509d93f8DDDC8C6FB",
    "0xD1220A0cf47c7B9Be7A2E6BA89F429762e7b9aDb"
  ]

  @single_case [
    "0x52908400098527886E0F7030069857D2E4169EE7",
    "0x8617E340B3D01FA5F11F306F4090FD50E238070D",
    "0xde709f2102306220921060314715629080e2fb77",
    "0x27b1fdb04752bbc536007a920d24acb045561c26"
  ]

  describe "Keccak-256" do
    test "agrees with the reference implementation, across the block boundary" do
      for {message, expected} <- [
            {"", "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"},
            {"abc", "4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45"},
            {"The quick brown fox jumps over the lazy dog",
             "4d741b6f1eb29cb2a9b9911c82f56fa8d73b04959d3d9d222895df6c0b28aa15"},
            {String.duplicate("y", 135),
             "381d81af29434d050b0d038b59157d96015ad07ad6f4267838db2d3c245d383a"},
            {String.duplicate("x", 136),
             "50da8ef3747b7a7f01d08563aa11c72a2a668563fb928adc6e8d2a1ab4e36096"},
            {String.duplicate("z", 137),
             "32fe0c7ccc0a26485fc1555eb4075da8b6c66da403bdf0fedb664a4a876d7a98"},
            {String.duplicate("a", 200),
             "96ea54061def936c4be90b518992fdc6f12f535068a256229aca54267b4d084d"}
          ] do
        assert Base.encode16(Keccak.hash(message), case: :lower) == expected
      end
    end

    test "is not SHA3-256, which the runtime does have" do
      refute Keccak.hash("abc") == :crypto.hash(:sha3_256, "abc")
    end
  end

  describe "an address that carries a checksum" do
    test "is accepted and stored in its lowercase form" do
      for address <- @checksummed do
        assert {:ok, String.downcase(address)} == Address.canonicalize(address)
      end
    end

    test "is refused when one character has the wrong case" do
      for address <- @checksummed do
        for damaged <- one_character_wrong(address) do
          assert {:error, :bad_checksum} == Address.canonicalize(damaged),
                 "#{damaged} was accepted"
        end
      end
    end

    test "is refused when one hexadecimal digit is wrong" do
      # 0x5aAeb...ed with its last digit changed. Changing a digit changes the
      # checksum of every letter, so the case that was right is now wrong.
      assert {:error, :bad_checksum} =
               Address.canonicalize("0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAec")
    end

    test "can be written back in the spelling it carries the checksum in" do
      for address <- @checksummed ++ @single_case do
        assert Address.checksummed(String.downcase(address)) ==
                 Address.checksummed(address)
      end

      for address <- @checksummed do
        assert Address.checksummed(String.downcase(address)) == address
      end
    end
  end

  describe "an address written in one case" do
    test "carries no checksum and is taken as given" do
      for address <- @single_case do
        assert {:ok, String.downcase(address)} == Address.canonicalize(address)
      end
    end
  end

  describe "an address that is not one" do
    test "is refused before anything is hashed" do
      for value <- [
            "",
            "0x",
            "de709f2102306220921060314715629080e2fb77",
            "0xde709f2102306220921060314715629080e2fb7",
            "0xde709f2102306220921060314715629080e2fb777",
            "0xde709f2102306220921060314715629080e2fb7g",
            "0Xde709f2102306220921060314715629080e2fb77",
            nil,
            42
          ] do
        assert {:error, :malformed} == Address.canonicalize(value), "#{inspect(value)} was read"
      end
    end

    test "may still be surrounded by whitespace a paste brought with it" do
      assert {:ok, "0xde709f2102306220921060314715629080e2fb77"} =
               Address.canonicalize("\n  0xde709f2102306220921060314715629080e2fb77\t ")
    end
  end

  # Every single-letter case flip of an address, which is the mistake the
  # checksum exists to catch.
  defp one_character_wrong(address) do
    "0x" <> hex = address

    for {character, index} <- Enum.with_index(String.to_charlist(hex)),
        character in ~c"abcdefABCDEF" do
      flipped =
        if character in ~c"abcdef", do: character - 32, else: character + 32

      "0x" <> (hex |> String.to_charlist() |> List.replace_at(index, flipped) |> List.to_string())
    end
  end
end
