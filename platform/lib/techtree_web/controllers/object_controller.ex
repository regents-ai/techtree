defmodule TechtreeWeb.ObjectController do
  @moduledoc """
  One content-addressed protocol object, byte for byte.

  A digest never becomes a path. It is checked for shape, looked up in the
  imported catalog, and only the catalog-relative path that lookup returns is
  resolved — under the bundle root, refusing links, and hashed again before a
  single byte is sent. A digest this application cannot resolve that way is a
  `404`, never a guess.

  Two fixed policies:

    * a digest that is not spelled `sha256:` followed by 64 lowercase
      hexadecimal characters is a malformed request, and answers `400`;
    * a digest that was published by an earlier release stays resolvable while
      its bytes remain in the bundle. A content address means the same thing
      forever, which is what the immutable caching header promises.
  """

  use TechtreeWeb, :controller

  alias Techtree.Catalog.Digest
  alias Techtree.Catalog.Query
  alias TechtreeWeb.ExactResponse

  @doc """
  Return the exact bytes filed under one digest.
  """
  def show(conn, %{"digest" => digest}) do
    if Digest.valid?(digest) do
      send_object(conn, digest)
    else
      ExactResponse.send_error(
        conn,
        400,
        :invalid_digest,
        "An object is addressed by sha256: followed by 64 lowercase hexadecimal characters.",
        false
      )
    end
  end

  defp send_object(conn, digest) do
    case Query.object_bytes(digest) do
      {:ok, bytes, entry} ->
        ExactResponse.send_exact(
          conn,
          bytes,
          entry.media_type,
          entry.protocol_digest,
          :immutable
        )

      {:error, error} ->
        ExactResponse.send_error(conn, error)
    end
  end
end
