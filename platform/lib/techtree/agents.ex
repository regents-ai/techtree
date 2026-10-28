defmodule Techtree.Agents do
  @moduledoc """
  Agents that sign in with a wallet. Signed in, an agent acts as itself; an active
  pairing permits the account actions its person allows while retaining the
  agent's identity. World ID is optional.
  """

  use Ash.Domain

  resources do
    resource Techtree.Agents.Agent do
      define :sign_in_agent, action: :sign_in, args: [:wallet_address]
      define :record_backing, action: :record_backing, args: [:human_id, :agent_count]
    end
  end
end
