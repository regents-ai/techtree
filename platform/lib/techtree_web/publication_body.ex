defmodule TechtreeWeb.PublicationBody do
  @moduledoc """
  Reading the body of the one request this site accepts, and refusing an
  oversized one before it is anything else.

  Two things are needed at the address that takes a body, and neither is
  needed anywhere else, so both happen here rather than in the pipeline
  everything passes through.

  *The exact bytes are kept.* A parsed body is not what was submitted — key
  order and whitespace are gone by then, and both documents that arrive here
  are checked against a digest of what arrived rather than against a
  re-rendering of it. So the bytes are set aside as they are read.

  *The size is capped as it arrives.* A body over the cap is stopped at the
  parser, which is before it has been decoded, before it has been hashed, and
  before anything has looked at what it claims to be. Nothing is spooled to
  disk on the way there, because there is no multipart parser on this site to
  spool it.

  The bytes are only kept for a request that arrived as `application/json`,
  because `Plug.Parsers` calls this reader for the parser that matched the
  content type and for nothing else. That is what makes the content type a gate
  rather than a check: a body sent as anything else is never read, and the
  address it was sent to finds no bytes and refuses.

  Every other address is left exactly as it was: no body is kept for one and no
  cap is imposed on it, because nothing reads one.
  """

  alias Techtree.Network

  @path "/api/v1/publications"

  @doc """
  Read a request body the way `Plug.Conn.read_body/2` does.

  For the one address that accepts one the bytes are also assigned to the
  connection, and a body over the cap is reported as one that did not finish —
  which is how `Plug.Parsers` is told that a body was too large.
  """
  @spec read_body(Plug.Conn.t(), keyword()) ::
          {:ok, binary(), Plug.Conn.t()}
          | {:more, binary(), Plug.Conn.t()}
          | {:error, term()}
  def read_body(%Plug.Conn{method: "POST", request_path: @path} = conn, options) do
    case Plug.Conn.read_body(conn, options) do
      {:ok, body, conn} ->
        if byte_size(body) <= Network.maximum_body_bytes() do
          {:ok, body, Plug.Conn.assign(conn, :submitted_bytes, body)}
        else
          {:more, body, conn}
        end

      other ->
        other
    end
  end

  def read_body(conn, options), do: Plug.Conn.read_body(conn, options)
end
