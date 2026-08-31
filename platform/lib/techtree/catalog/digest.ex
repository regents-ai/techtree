defmodule Techtree.Catalog.Digest do
  @moduledoc """
  Content addresses over raw catalog bytes.

  Every protocol object in a Techtree catalog is addressed by the SHA-256 of the
  exact bytes `techtree-python` generated. This module hashes those bytes and
  nothing else: it does not canonicalize JSON, and it never decodes an object in
  order to re-encode it. Byte equality is the whole contract, so a document that
  differs only in whitespace is a different object here — which is the point,
  because the website republishes bytes it did not produce.

  A digest is spelled `sha256:` followed by exactly 64 lowercase hexadecimal
  characters. Uppercase is rejected rather than downcased: a caller asking for
  a digest the catalog does not spell that way is asking for something else.
  """

  @prefix "sha256:"
  @hex_length 64

  @doc """
  Whether a value is a digest this catalog can address an object by.

      iex> Techtree.Catalog.Digest.valid?(Techtree.Catalog.Digest.hash_bytes("{}"))
      true

      iex> Techtree.Catalog.Digest.valid?("sha256:ABC")
      false
  """
  @spec valid?(term()) :: boolean()
  def valid?(@prefix <> hex) when byte_size(hex) == @hex_length, do: lowercase_hex?(hex)
  def valid?(_other), do: false

  @doc """
  The 32 raw bytes a digest names, or a raise if it is not a digest.
  """
  @spec parse!(String.t()) :: binary()
  def parse!(digest) do
    if valid?(digest) do
      digest |> binary_part(byte_size(@prefix), @hex_length) |> Base.decode16!(case: :lower)
    else
      raise ArgumentError, "expected a sha256:<64 lowercase hex> digest, got: #{inspect(digest)}"
    end
  end

  @doc """
  The digest of exactly these bytes.

      iex> Techtree.Catalog.Digest.hash_bytes("")
      "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
  """
  @spec hash_bytes(binary()) :: String.t()
  def hash_bytes(bytes) when is_binary(bytes) do
    @prefix <> Base.encode16(:crypto.hash(:sha256, bytes), case: :lower)
  end

  @doc """
  Whether these bytes are the object filed under this digest.

  Returns `{:error, computed_digest}` on a mismatch so that the caller can
  report both sides of the disagreement. The comparison is constant time; the
  digests are public, but the habit is cheap and the code is copied.
  """
  @spec verify_bytes(binary(), String.t()) :: :ok | {:error, String.t()}
  def verify_bytes(bytes, digest) do
    computed = hash_bytes(bytes)

    if valid?(digest) and Plug.Crypto.secure_compare(computed, digest) do
      :ok
    else
      {:error, computed}
    end
  end

  defp lowercase_hex?(hex) do
    for <<character <- hex>>, reduce: true do
      acc -> acc and character in ~c"0123456789abcdef"
    end
  end
end
