defmodule TechtreeWeb.PrivyProof do
  @moduledoc """
  The Privy proof pair a request presents. The access token travels only as the
  bearer and the identity token only as Privy's own header, so neither reaches a
  URL, a body or a log. Exactly one of each is a pair; anything else is refused
  before the provider is asked.
  """

  import Plug.Conn, only: [get_req_header: 2]

  @doc "The request's `%{access: _, identity: _}`, or which half is missing."
  def pair(conn) do
    with {:ok, access} <- bearer_token(conn),
         {:ok, identity} <- identity_token(conn),
         do: {:ok, %{access: access, identity: identity}}
  end

  defp bearer_token(conn) do
    case get_req_header(conn, "authorization") do
      ["Bearer " <> access] -> present(access, :missing_access_token)
      _absent_or_duplicated -> {:error, {:request_pair, :missing_access_token}}
    end
  end

  defp identity_token(conn) do
    case get_req_header(conn, "privy-id-token") do
      [identity] -> present(identity, :missing_identity_token)
      _absent_or_duplicated -> {:error, {:request_pair, :missing_identity_token}}
    end
  end

  defp present(token, reason) do
    case String.trim(token) do
      "" -> {:error, {:request_pair, reason}}
      token -> {:ok, token}
    end
  end
end
