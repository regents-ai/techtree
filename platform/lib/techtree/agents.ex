defmodule Techtree.Agents do
  @moduledoc """
  Agents that sign in with a wallet. Signed in, an agent acts as itself; an active
  pairing permits the account actions its person allows while retaining the
  agent's identity. World ID is optional. An app a person connects to their
  account here, such as Claude, keeps one identity of its own through the hosted
  MCP server's identity tools (`Techtree.Agents.Connection`).
  """

  use Ash.Domain, extensions: [AshAi]

  # The hosted MCP server's identity tools, for an app a person connected to their
  # account here, with the titles, words and hints every Regent site gives them.
  @identity Map.new(RegentMCPAgents.Tools.list(), &{&1.name, &1})

  tools do
    for name <- RegentMCPAgents.Tools.names() do
      %{title: title, description: description, annotations: hints} = @identity[name]
      name = String.to_atom(name)

      tool name, Techtree.Agents.Connection, name do
        title(title)
        description description

        annotations(
          read_only_hint: hints.readOnlyHint,
          idempotent_hint: hints.idempotentHint,
          destructive_hint: hints.destructiveHint,
          open_world_hint: hints.openWorldHint
        )
      end
    end
  end

  resources do
    resource Techtree.Agents.Agent do
      define :sign_in_agent, action: :sign_in, args: [:wallet_address]
      define :record_backing, action: :record_backing, args: [:human_id, :agent_count]
    end

    resource Techtree.Agents.Connection
  end
end
