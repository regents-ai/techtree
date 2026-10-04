defmodule Techtree.WalletBench.Machine.Changes.RestoreBaseline do
  @moduledoc """
  Puts the machine's disk back to its baseline. Sprites sometimes refuses a
  restore made just after a checkpoint; the job's retries try it again.
  """

  use Ash.Resource.Change

  import Techtree.WalletBench.Machine.Changes.RecordEvent, only: [put_detail: 2]

  @impl true
  def change(changeset, _opts, _context) do
    Ash.Changeset.before_transaction(changeset, fn changeset ->
      machine = changeset.data

      case RegentSprites.restore(machine.name, machine.baseline_checkpoint_id) do
        :ok -> put_detail(changeset, %{checkpoint_id: machine.baseline_checkpoint_id})
        {:error, error} -> Ash.Changeset.add_error(changeset, error)
      end
    end)
  end
end
