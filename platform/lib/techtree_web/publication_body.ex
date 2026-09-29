defmodule TechtreeWeb.PublicationBody do
  @moduledoc """
  Reading the body of a publication or an agent's pairing request, and keeping
  its exact bytes.

  Nothing else on this site needs the bytes kept, so it happens here rather
  than in the pipeline everything passes through.

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

  `TechtreeWeb.PublicationAddress` decides which requests those are. An
  agent's pairing request is signed over its exact bytes too, so those are kept
  as `raw_body`, where `RegentAgents.HTTP` reads them. Every other address is
  read as it always was, and no body is kept for one.
  """

  alias TechtreeWeb.PublicationAddress

  @doc """
  Read a request body the way `Plug.Conn.read_body/2` does.

  For the publication address and an agent's pairing request the bytes are
  also assigned to the connection.
  """
  @spec read_body(Plug.Conn.t(), keyword()) ::
          {:ok, binary(), Plug.Conn.t()}
          | {:more, binary(), Plug.Conn.t()}
          | {:error, term()}
  def read_body(conn, options) do
    cond do
      PublicationAddress.post?(conn) -> keep(conn, options, :submitted_bytes)
      agent_pairing?(conn) -> keep(conn, options, :raw_body)
      true -> RegentIdentity.BodyReader.read_body(conn, options)
    end
  end

  defp agent_pairing?(%Plug.Conn{method: "POST", path_info: ["api", "agents", "v1", "pair"]}),
    do: true

  defp agent_pairing?(%Plug.Conn{}), do: false

  defp keep(conn, options, name) do
    case Plug.Conn.read_body(conn, options) do
      {:ok, body, conn} -> {:ok, body, Plug.Conn.assign(conn, name, body)}
      other -> other
    end
  end
end
