defmodule Techtree.Network.Address do
  @moduledoc """
  Reading an Ethereum address somebody typed, and refusing one they mistyped.

  An address is not a name. Nobody notices a wrong character in it, no service
  will bounce a transfer sent to a wrong-but-well-formed one, and there is no
  way back afterwards. EIP-55 exists for exactly that reason: it hides a
  checksum in the *case* of the hexadecimal letters, so an address copied from
  anywhere that spells it the modern way can be checked before it is stored.
  The check costs one hash of forty characters, so there is no argument for
  skipping it.

  Case is also why an address needs canonicalising at all. The same account can
  be written all lowercase, all uppercase, or checksummed, and all three are the
  same account. Only the lowercase spelling is stored, so one address given
  twice in two spellings is one record rather than two.

  What is *not* checked is whoever typed it. A string is not proof of control of
  an account, and this module makes no claim that it is. Signing for an address
  is a different thing, and when it arrives it will be a different kind of
  attestation beside this one rather than a repair of it.
  """

  alias Techtree.Network.Keccak

  @length 40

  @typedoc """
  Why an address was refused.
  """
  @type reason :: :malformed | :bad_checksum

  @doc """
  The canonical lowercase form of an address, or why it was refused.

      iex> Techtree.Network.Address.canonicalize("  0xde709f2102306220921060314715629080e2fb77 ")
      {:ok, "0xde709f2102306220921060314715629080e2fb77"}

      iex> Techtree.Network.Address.canonicalize("0x5aAeb6053f3E94C9b9A09f33669435E7Ef1BeAed")
      {:error, :bad_checksum}
  """
  @spec canonicalize(term()) :: {:ok, String.t()} | {:error, reason()}
  def canonicalize(value) when is_binary(value) do
    with {:ok, hex} <- shape(String.trim(value)) do
      checksum(hex)
    end
  end

  def canonicalize(_value), do: {:error, :malformed}

  @doc """
  The EIP-55 spelling of an address: the same characters, in the case that
  carries the checksum.
  """
  @spec checksummed(String.t()) :: String.t()
  def checksummed("0x" <> hex) do
    lower = String.downcase(hex)

    "0x" <>
      (lower
       |> String.to_charlist()
       |> Enum.zip(nibbles(lower))
       |> Enum.map_join(fn {character, nibble} ->
         if nibble >= 8, do: <<upcase(character)>>, else: <<character>>
       end))
  end

  # -- Internals ------------------------------------------------------------

  defp shape("0x" <> hex) when byte_size(hex) == @length do
    if hexadecimal?(hex), do: {:ok, "0x" <> hex}, else: {:error, :malformed}
  end

  defp shape(_value), do: {:error, :malformed}

  # An address written entirely in one case carries no checksum to check —
  # that is the older spelling, and EIP-55 says so. A mixed-case address is
  # claiming to carry one, and is taken at its word.
  defp checksum("0x" <> hex = address) do
    lower = "0x" <> String.downcase(hex)

    cond do
      hex == String.downcase(hex) -> {:ok, lower}
      hex == String.upcase(hex) -> {:ok, lower}
      checksummed(lower) == address -> {:ok, lower}
      true -> {:error, :bad_checksum}
    end
  end

  # The checksum is the Keccak-256 of the lowercase characters, read one
  # hexadecimal digit per character of the address.
  defp nibbles(lower) do
    Keccak.hash(lower)
    |> Base.encode16(case: :lower)
    |> String.to_charlist()
    |> Enum.take(@length)
    |> Enum.map(&List.to_integer([&1], 16))
  end

  defp upcase(character) when character in ?a..?f, do: character - 32
  defp upcase(character), do: character

  defp hexadecimal?(hex) do
    for <<character <- hex>>, reduce: true do
      acc -> acc and character in ~c"0123456789abcdefABCDEF"
    end
  end
end
