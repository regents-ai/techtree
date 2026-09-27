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

  The size cap is not here: the parser in `TechtreeWeb.Endpoint` reads no more
  than the cap from any address, and stops a body over it before it has been
  decoded, hashed or looked at.

  The bytes are only kept for a request that arrived as `application/json`,
  because `Plug.Parsers` calls this reader for the parser that matched the
  content type and for nothing else. That is what makes the content type a gate
  rather than a check: a body sent as anything else is never read, and the
  address it was sent to finds no bytes and refuses.

  `TechtreeWeb.PublicationAddress` decides which requests those are. Every
  other address is read as it always was, and no body is kept for one.
  """

  alias TechtreeWeb.PublicationAddress

  @doc """
  Read a request body the way `Plug.Conn.read_body/2` does.

  For the one address that accepts one the bytes are also assigned to the
  connection.
  """
  @spec read_body(Plug.Conn.t(), keyword()) ::
          {:ok, binary(), Plug.Conn.t()}
          | {:more, binary(), Plug.Conn.t()}
          | {:error, term()}
  def read_body(conn, options) do
    if PublicationAddress.post?(conn),
      do: keep(conn, options),
      else: RegentIdentity.BodyReader.read_body(conn, options)
  end

  defp keep(conn, options) do
    case Plug.Conn.read_body(conn, options) do
      {:ok, body, conn} -> {:ok, body, Plug.Conn.assign(conn, :submitted_bytes, body)}
      other -> other
    end
  end
end
