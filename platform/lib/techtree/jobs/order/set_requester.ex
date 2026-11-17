defmodule Techtree.Jobs.Order.SetRequester do
  @moduledoc """
  Makes the signed agent the order's requester, and its person the order's
  person while the two are paired. Nothing a caller sends names either.
  """

  use Ash.Resource.Change

  alias Techtree.Actors.Agent

  @impl true
  def change(changeset, _opts, %{actor: %Agent{} = agent}) do
    Ash.Changeset.force_change_attributes(changeset,
      agent_id: agent.agent_id,
      human_account_id: if(agent.pairing == :active, do: agent.human_account_id)
    )
  end

  # Anyone else is refused by the action's policy.
  def change(changeset, _opts, _context), do: changeset
end
