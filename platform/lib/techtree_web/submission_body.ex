defmodule TechtreeWeb.SubmissionBody do
  @moduledoc """
  Reading the body of the one request this site accepts, and refusing an
  oversized one before it is anything else.

  Two things are needed at the one address that takes a body, and neither is
  needed anywhere else, so both happen here rather than in the pipeline
  everything passes through.

  *The exact bytes are kept.* A parsed body is not what was submitted — key
  order and whitespace are gone by then, and the endpoint that serves a
  submission back has to serve what arrived, not a re-rendering of it. So the
  bytes are set aside as they are read.

  *The size is capped as it arrives.* A body over the cap is stopped at the
  parser, which is before it has been decoded, before it has been hashed, and
  before anything has looked at what it claims to be. Nothing is spooled to
  disk on the way there, because there is no multipart parser on this site to
  spool it.

  Every other address is left exactly as it was: no body is kept for it and no
  cap is imposed on it, because nothing reads one.
  """

  alias Techtree.Network

  @path "/api/v1/submissions"

  @doc """
  Read a request body the way `Plug.Conn.read_body/2` does.

  For the submission address the bytes are also assigned to the connection, and
  a body over the cap is reported as one that did not finish — which is how
  `Plug.Parsers` is told that a body was too large.
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
