defmodule Techtree.Canonical do
  @moduledoc """
  Writing a decoded JSON document back out the way the protocol hashes it.

  Every digest inside a Techtree proof is the SHA-256 of the RFC 8785 canonical
  form of the object it names, and `techtree-python` is the implementation that
  produced them. This site never signs anything, but it does have to *check* a
  signature, and checking one means recomputing a `payload_digest` from a
  payload it parsed out of a submission. So the two implementations have to
  agree byte for byte. One byte of disagreement is not a subtle bug — it
  rejects every honest submission there will ever be — which is why this module
  is pinned to the other one by a golden test over a real proof bundle rather
  than by anybody's reading of the specification.

  RFC 8785 fixes three things, and each is a place where two implementations
  can plausibly differ.

  *Key order.* Object members are sorted by the UTF-16 code units of their
  names, not by their UTF-8 bytes. The two orders agree for everything below
  U+FFFF and disagree above it, because UTF-16 spells those as surrogates that
  sort below the highest ordinary characters. Sorting the UTF-8 bytes would
  look right for years and then be wrong the first time an emoji appeared in a
  key.

  *Strings.* Only the backslash, the double quote, and the C0 control
  characters are escaped, the seven with short forms in their short form and
  the rest as lowercase `\\u00xx`. Everything else — accents, ideographs,
  emoji, the solidus, the delete character — is emitted as its own UTF-8 bytes.
  A JSON writer that escapes more than that is still writing valid JSON and is
  still writing the wrong bytes.

  *Numbers.* This is the whole of the difficulty. JSON's number is an IEEE-754
  double, and canonical form is what ECMAScript's `Number::toString` makes of
  one: the shortest decimal that reads back as the same double, laid out
  positionally when the exponent is in range and in exponential form when it is
  not. That is why an integer written `1.0` comes back as `1`, why `1e20`
  becomes twenty-one digits, and why `1e21` stays exponential. Every number is
  taken as a double, integers included: the specification says a JSON number is
  a double, and treating a literal like `100000000000000000000` as anything
  else would fail to reproduce the canonical text of the very value it is the
  canonical text of.

  Nothing here decides what a document *means*. It takes the values a JSON
  parser produced and writes them back; a caller that wants a digest hashes the
  result.
  """

  # A double has no decimal exponent outside this window that ECMAScript
  # spells positionally.
  @positional_maximum 21
  @positional_minimum -6

  @typedoc """
  Why a value has no canonical spelling.
  """
  @type reason :: :unrepresentable_number | :unsupported_value

  @doc """
  The canonical bytes of one decoded JSON value.

      iex> Techtree.Canonical.encode(%{"b" => 1, "a" => [1.0, "x"]})
      {:ok, ~s({"a":[1,"x"],"b":1})}
  """
  @spec encode(term()) :: {:ok, binary()} | {:error, reason()}
  def encode(value) do
    {:ok, value |> write() |> IO.iodata_to_binary()}
  catch
    {__MODULE__, reason} -> {:error, reason}
  end

  @doc """
  The canonical bytes, or a raise when the value has none.
  """
  @spec encode!(term()) :: binary()
  def encode!(value) do
    case encode(value) do
      {:ok, bytes} -> bytes
      {:error, reason} -> raise ArgumentError, "value has no canonical JSON form: #{reason}"
    end
  end

  # -- Values ---------------------------------------------------------------

  defp write(nil), do: "null"
  defp write(true), do: "true"
  defp write(false), do: "false"
  defp write(value) when is_binary(value), do: string(value)
  defp write(value) when is_integer(value), do: number(to_double(value))
  defp write(value) when is_float(value), do: number(value)
  defp write([]), do: "[]"
  defp write(value) when is_list(value), do: [?[, Enum.map_intersperse(value, ?,, &write/1), ?]]

  defp write(value) when is_map(value) and not is_struct(value) and map_size(value) == 0, do: "{}"

  defp write(value) when is_map(value) and not is_struct(value) do
    members =
      value
      |> Enum.sort_by(fn {key, _value} -> sort_key(key) end)
      |> Enum.map_intersperse(?,, fn {key, member} -> [string(key), ?:, write(member)] end)

    [?{, members, ?}]
  end

  defp write(_value), do: throw({__MODULE__, :unsupported_value})

  # Member names are ordered by their UTF-16 code units, big-endian, which is
  # not the order their UTF-8 bytes are in for anything outside the basic
  # plane.
  defp sort_key(key) when is_binary(key) do
    case :unicode.characters_to_binary(key, :utf8, {:utf16, :big}) do
      encoded when is_binary(encoded) -> encoded
      _other -> throw({__MODULE__, :unsupported_value})
    end
  end

  defp sort_key(_key), do: throw({__MODULE__, :unsupported_value})

  # -- Strings --------------------------------------------------------------

  defp string(value), do: [?", escape(value, value, 0), ?"]

  # Each step carries the original binary and the length of the run of bytes
  # that need no escaping, so an unescaped string is copied once rather than
  # rebuilt byte by byte.
  defp escape(<<>>, original, length), do: binary_part(original, 0, length)

  defp escape(<<byte, rest::binary>>, original, length) when byte in [?", ?\\] or byte < 0x20 do
    [binary_part(original, 0, length), escaped(byte) | escape(rest, rest, 0)]
  end

  defp escape(<<_byte, rest::binary>>, original, length), do: escape(rest, original, length + 1)

  defp escaped(?"), do: ~S(\")
  defp escaped(?\\), do: ~S(\\)
  defp escaped(?\b), do: ~S(\b)
  defp escaped(?\f), do: ~S(\f)
  defp escaped(?\n), do: ~S(\n)
  defp escaped(?\r), do: ~S(\r)
  defp escaped(?\t), do: ~S(\t)

  defp escaped(byte),
    do: [
      "\\u00",
      byte |> Integer.to_string(16) |> String.downcase() |> String.pad_leading(2, "0")
    ]

  # -- Numbers --------------------------------------------------------------

  defp to_double(value) do
    :erlang.float(value)
  rescue
    ArgumentError -> throw({__MODULE__, :unrepresentable_number})
  end

  # ECMAScript spells both zeros `0`, and a JSON document cannot carry a NaN or
  # an infinity for one to be spelled at all.
  defp number(value) when value == 0.0, do: "0"
  defp number(value) when value < 0.0, do: [?-, number(-value)]

  defp number(value) do
    {digits, exponent} = shortest(value)
    width = byte_size(digits)

    cond do
      width <= exponent and exponent <= @positional_maximum ->
        [digits, zeros(exponent - width)]

      exponent > 0 and exponent <= @positional_maximum ->
        [binary_part(digits, 0, exponent), ?., binary_part(digits, exponent, width - exponent)]

      exponent > @positional_minimum and exponent <= 0 ->
        ["0.", zeros(-exponent), digits]

      width == 1 ->
        [digits, exponential(exponent)]

      true ->
        [binary_part(digits, 0, 1), ?., binary_part(digits, 1, width - 1), exponential(exponent)]
    end
  end

  defp exponential(exponent) do
    place = exponent - 1
    [?e, if(place < 0, do: ?-, else: ?+), Integer.to_string(abs(place))]
  end

  defp zeros(0), do: []
  defp zeros(count), do: :binary.copy("0", count)

  # The shortest decimal that reads back as this double, as its significant
  # digits and the decimal exponent that places the point in front of them:
  # `{"5255841 69", 3}` means 0.525584169 × 10³. The runtime already knows the
  # shortest digits; the layout is this module's business, not the runtime's,
  # so its spelling is taken apart rather than trusted.
  defp shortest(value) do
    [mantissa | rest] = :erlang.float_to_binary(value, [:short]) |> :binary.split("e")
    [whole, fraction] = :binary.split(mantissa, ".")

    exponent =
      case rest do
        [] -> 0
        [written] -> String.to_integer(written)
      end

    trim(whole <> fraction, byte_size(whole) + exponent)
  end

  defp trim(<<?0, rest::binary>>, exponent) when rest != <<>>, do: trim(rest, exponent - 1)

  # Nothing is stripped from the front but zeros, so what is left begins with a
  # significant digit and stripping the trailing zeros cannot empty it.
  defp trim(digits, exponent), do: {String.trim_trailing(digits, "0"), exponent}
end
