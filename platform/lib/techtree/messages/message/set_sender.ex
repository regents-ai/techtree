defmodule Techtree.Messages.Message.SetSender do
  @moduledoc """
  Makes the actor the message's sender: a signed-in person, with the agent acting
  for them if one is; or a signed agent, with its person once paired. Nothing a
  caller sends can name the sender.
  """

  use Ash.Resource.Change

  alias Techtree.Actors.{Agent, Human}

  @impl true
  def change(changeset, _opts, %{actor: %Human{} = human}) do
    Ash.Changeset.force_change_attributes(changeset,
      human_account_id: human.human_account_id,
      agent_id: human.acting_agent_id,
      sender_name: human.name
    )
  end

  def change(changeset, _opts, %{actor: %Agent{} = agent}) do
    Ash.Changeset.force_change_attributes(changeset,
      human_account_id: if(agent.pairing == :active, do: agent.human_account_id),
      agent_id: agent.agent_id,
      sender_name: agent.name
    )
  end

  # Anyone else is refused by the action's policy.
  def change(changeset, _opts, _context), do: changeset
end
