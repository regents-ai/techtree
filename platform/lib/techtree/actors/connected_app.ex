defmodule Techtree.Actors.ConnectedApp do
  @moduledoc """
  An app a person connected to their account here, such as Claude, calling the
  hosted MCP server with the token its connection holds. `principal` is what
  `RegentOAuth.verify/3` answered for that token: the person's subject, the
  token, the client and the scopes the person approved. It may use only the
  connection's identity tools (`Techtree.Agents.Connection`). Once that
  identity is paired with the person's account and the person allowed the
  site's agent permission, the app calls as its paired agent instead
  (`Techtree.Actors.Agent`, `connection`).
  """
  @enforce_keys [:principal]
  defstruct [:principal, role: :connected_app]
end
