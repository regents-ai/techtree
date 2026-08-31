defmodule Techtree.Network.Keccak do
  @moduledoc """
  Keccak-256, because Ethereum's address checksum is computed with it and
  nothing else computes it.

  This looks at first like something the runtime already has. It is not.
  Erlang's `:crypto` offers SHA3-256, which is the same permutation with a
  different pad byte — SHA-3 appends `0x06` where the original Keccak
  submission appends `0x01` — and Ethereum froze the original. The two hashes
  agree on nothing, and one cannot be derived from the other, so the function
  is written out here rather than reached for.

  It is used for exactly one thing: checking that a mixed-case Ethereum address
  somebody typed carries the checksum EIP-55 says it should. That is a single
  40-character message, once, so this is written to be read rather than to be
  fast. The whole of the permutation is here: five steps, twenty-four rounds,
  twenty-five sixty-four-bit lanes, and the constants those steps are defined
  by. It is pinned to the published test vectors rather than to a reading of
  the specification.
  """

  import Bitwise

  @lane 0xFFFFFFFFFFFFFFFF
  @lanes 25

  # Keccak-256 absorbs 1088 bits at a time and returns the first 256.
  @rate 136
  @digest_bytes 32

  # The iota constants, one per round.
  @round_constants [
    0x0000000000000001,
    0x0000000000008082,
    0x800000000000808A,
    0x8000000080008000,
    0x000000000000808B,
    0x0000000080000001,
    0x8000000080008081,
    0x8000000000008009,
    0x000000000000008A,
    0x0000000000000088,
    0x0000000080008009,
    0x000000008000000A,
    0x000000008000808B,
    0x800000000000008B,
    0x8000000000008089,
    0x8000000000008003,
    0x8000000000008002,
    0x8000000000000080,
    0x000000000000800A,
    0x800000008000000A,
    0x8000000080008081,
    0x8000000000008080,
    0x0000000080000001,
    0x8000000080008008
  ]

  # The rho rotations, read as r[x][y].
  @rotations {
    {0, 36, 3, 41, 18},
    {1, 44, 10, 45, 2},
    {62, 6, 43, 15, 61},
    {28, 55, 25, 21, 56},
    {27, 20, 39, 8, 14}
  }

  # Rho and pi together: where each lane goes, and how far it turns on the way.
  # A lane is addressed by `x + 5y`, and pi sends the lane at (x, y) to
  # (y, 2x + 3y).
  @permutation for x <- 0..4,
                   y <- 0..4,
                   do:
                     {y + 5 * rem(2 * x + 3 * y, 5), x + 5 * y, @rotations |> elem(x) |> elem(y)}

  @doc """
  The Keccak-256 digest of these bytes, as 32 raw bytes.
  """
  @spec hash(binary()) :: binary()
  def hash(message) when is_binary(message) do
    message
    |> pad()
    |> absorb(Tuple.duplicate(0, @lanes))
    |> squeeze()
  end

  # The original Keccak padding: the message is filled out to a whole block by
  # a `0x01` byte, zeros, and a high bit set in the block's last byte. Where
  # only one byte is missing those are the same byte. SHA-3 differs from this
  # and only from this.
  defp pad(message) do
    case @rate - rem(byte_size(message), @rate) do
      1 -> message <> <<0x81>>
      filling -> message <> <<0x01>> <> :binary.copy(<<0>>, filling - 2) <> <<0x80>>
    end
  end

  defp absorb(<<>>, state), do: state

  defp absorb(<<block::binary-size(@rate), rest::binary>>, state) do
    absorb(rest, block |> soak(state, 0) |> permute())
  end

  defp soak(<<>>, state, _index), do: state

  defp soak(<<word::little-unsigned-64, rest::binary>>, state, index) do
    soak(rest, put_elem(state, index, bxor(elem(state, index), word)), index + 1)
  end

  defp squeeze(state) do
    for index <- 0..(div(@digest_bytes, 8) - 1), into: <<>> do
      <<elem(state, index)::little-unsigned-64>>
    end
  end

  defp permute(state), do: Enum.reduce(@round_constants, state, &round/2)

  defp round(constant, state) do
    state
    |> theta()
    |> rho_and_pi()
    |> chi()
    |> iota(constant)
  end

  # Each column is folded into one lane, and every lane in a column takes the
  # parity of its two neighbouring columns.
  defp theta(state) do
    columns =
      for x <- 0..4 do
        Enum.reduce(0..4, 0, fn y, acc -> bxor(acc, elem(state, x + 5 * y)) end)
      end

    columns = List.to_tuple(columns)

    lanes =
      for x <- 0..4 do
        bxor(
          elem(columns, rem(x + 4, 5)),
          rotate(elem(columns, rem(x + 1, 5)), 1)
        )
      end

    lanes = List.to_tuple(lanes)

    Enum.reduce(0..(@lanes - 1), state, fn index, acc ->
      put_elem(acc, index, bxor(elem(acc, index), elem(lanes, rem(index, 5))))
    end)
  end

  defp rho_and_pi(state) do
    Enum.reduce(@permutation, state, fn {destination, source, rotation}, acc ->
      put_elem(acc, destination, rotate(elem(state, source), rotation))
    end)
  end

  # Every lane is combined with the two lanes along its row.
  defp chi(state) do
    Enum.reduce(0..4, state, fn y, acc ->
      row = for x <- 0..4, do: elem(state, x + 5 * y)
      row = List.to_tuple(row)

      Enum.reduce(0..4, acc, fn x, inner ->
        combined =
          bxor(
            elem(row, x),
            bnot(elem(row, rem(x + 1, 5))) &&& elem(row, rem(x + 2, 5))
          )

        put_elem(inner, x + 5 * y, combined)
      end)
    end)
  end

  defp iota(state, constant), do: put_elem(state, 0, bxor(elem(state, 0), constant))

  defp rotate(lane, 0), do: lane

  defp rotate(lane, places),
    do: (lane <<< places ||| lane >>> (64 - places)) &&& @lane
end
