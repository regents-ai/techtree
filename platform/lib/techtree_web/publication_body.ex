defmodule TechtreeWeb.PublicationBody do
  @moduledoc """
  Reading the body of a publication or any other request to the API, and
  keeping its exact bytes.

  The pages' own form bodies need nothing kept, so it happens here rather than
  in the pipeline everything passes through.

  *The exact bytes are kept.* A parsed body is not what was submitted — key
  order and whitespace are gone by then, and both documents that arrive here
  are checked against a digest of what arrived rather than against a
  re-rendering of it. So the bytes are set aside as they are read.

  The parser and shared SIWA body reader enforce the existing publication cap
  before parsing or verification. Every other body the API takes has a smaller
  8,192-byte cap, the size of the largest, a private profile.

  The bytes are only kept for a request that arrived as `application/json`,
  because `Plug.Parsers` calls this reader for the parser that matched the
  content type and for nothing else. That is what makes the content type a gate
  rather than a check: a body sent as anything else is never read, and the
  address it was sent to finds no bytes and refuses.

  `TechtreeWeb.PublicationAddress` decides which requests those are. Any other
  POST or PATCH under `/api` may come from an agent too, signed over its exact
  bytes, so the sign-in library's own reader keeps them, up to 8,192 bytes, and
  marks them as the whole body; `TechtreeWeb.Plugs.AgentWallet` and
  `RegentAgents.HTTP` check them there. Every other address uses the identity
  body reader as before.
  """

  alias TechtreeWeb.PublicationAddress

  # The largest of these is a private profile, which
  # `RegentIdentity.BodyReader` caps at the same size.
  @signed_maximum_bytes 8192

  @doc """
  Read a request body the way `Plug.Conn.read_body/2` does.

  For the publication address and a request to the API the bytes are also
  assigned to the connection.
  """
  @spec read_body(Plug.Conn.t(), keyword()) ::
          {:ok, binary(), Plug.Conn.t()}
          | {:more, binary(), Plug.Conn.t()}
          | {:error, term()}
  def read_body(conn, options) do
    cond do
      PublicationAddress.post?(conn) -> publication_body(conn, options)
      PublicationAddress.model_climb_post?(conn) -> model_climb_body(conn, options)
      signed?(conn) -> Siwa.AgentAuthPlug.read_body(conn, options, @signed_maximum_bytes)
      true -> RegentIdentity.BodyReader.read_body(conn, options)
    end
  end

  defp signed?(%{method: method, path_info: path_info}) when method in ["POST", "PATCH"],
    do: match?(["api" | _], Enum.map(path_info, &URI.decode/1))

  defp signed?(_conn), do: false

  defp model_climb_body(conn, options),
    do: Siwa.AgentAuthPlug.read_body(conn, options, Techtree.ModelClimb.Proof.maximum_bytes())

  defp publication_body(conn, options) do
    case Siwa.AgentAuthPlug.read_body(conn, options, Techtree.Network.maximum_body_bytes()) do
      {:ok, body, conn} -> {:ok, body, Plug.Conn.assign(conn, :submitted_bytes, body)}
      other -> other
    end
  end
end
