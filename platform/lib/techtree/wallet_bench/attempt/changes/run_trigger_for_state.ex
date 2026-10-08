defmodule Techtree.WalletBench.Attempt.Changes.RunTriggerForState do
  @moduledoc """
  Queues the next step's job for the state a step ended in, in the same
  transaction, for steps that can end in more than one state. Takes the states
  and their triggers, such as `sending: :send_funding, revoking: :revoke`.
  """

  use Ash.Resource.Change

  @impl true
  def change(changeset, opts, _context) do
    Ash.Changeset.after_action(changeset, fn _changeset, attempt ->
      if trigger = opts[attempt.state], do: AshOban.run_trigger(attempt, trigger)
      {:ok, attempt}
    end)
  end
end
