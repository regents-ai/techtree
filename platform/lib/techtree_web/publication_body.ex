defmodule TechtreeWeb.PublicationBody do
  @moduledoc """
  Reading the body of a publication or an agent's request, and keeping its
  exact bytes.

  Nothing else on this site needs the bytes kept, so it happens here rather
  than in the pipeline everything passes through.

  *The exact bytes are kept.* A parsed body is not what was submitted — key
  order and whitespace are gone by then, and both documents that arrive here
  are checked against a digest of what arrived rather than against a
  re-rendering of it. So the bytes are set aside as they are read.

  The parser and shared SIWA body reader enforce the existing publication cap
  before parsing or verification. Signed account and pairing bodies have a
  smaller 4096-byte cap.

  The bytes are only kept for a request that arrived as `application/json`,
  because `Plug.Parsers` calls this reader for the parser that matched the
  content type and for nothing else. That is what makes the content type a gate
  rather than a check: a body sent as anything else is never read, and the
  address it was sent to finds no bytes and refuses.

  `TechtreeWeb.PublicationAddress` decides which requests those are. An
  agent's request to `/api/agents` is signed over its exact bytes too, so the
  sign-in library's own reader keeps them, up to 4096 bytes, and marks them as
  the whole body; `RegentAgents.HTTP` checks them there. Signed `/tools/account` bodies use that same reader and cap. Every other
  address uses the identity body reader as before.
  """

  alias TechtreeWeb.PublicationAddress

  @agent_maximum_bytes 4096

  @doc """
  Read a request body the way `Plug.Conn.read_body/2` does.

  For the publication address and an agent's request the bytes are also
  assigned to the connection.
  """
  @spec read_body(Plug.Conn.t(), keyword()) ::
          {:ok, binary(), Plug.Conn.t()}
          | {:more, binary(), Plug.Conn.t()}
          | {:error, term()}
  def read_body(conn, options) do
    cond do
      PublicationAddress.post?(conn) -> publication_body(conn, options)
      agent_request?(conn) -> Siwa.AgentAuthPlug.read_body(conn, options, @agent_maximum_bytes)
      true -> RegentIdentity.BodyReader.read_body(conn, options)
    end
  end

  defp agent_request?(conn) do
    case Enum.map(conn.path_info, &URI.decode/1) do
      ["api", "agents" | _] -> true
      ["tools", "account" | _] -> true
      _other -> false
    end
  end

  defp publication_body(conn, options) do
    case Siwa.AgentAuthPlug.read_body(conn, options, Techtree.Network.maximum_body_bytes()) do
      {:ok, body, conn} -> {:ok, body, Plug.Conn.assign(conn, :submitted_bytes, body)}
      other -> other
    end
  end
end
