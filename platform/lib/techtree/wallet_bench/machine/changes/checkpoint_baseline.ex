defmodule Techtree.WalletBench.Machine.Changes.CheckpointBaseline do
  @moduledoc """
  Saves the new machine's disk as its baseline. The checkpoint's comment names
  the machine record, so a repeated job finds the checkpoint its earlier run made.
  """

  use Ash.Resource.Change

  import Techtree.WalletBench.Machine.Changes.RecordEvent, only: [put_detail: 2]

  @impl true
  def change(changeset, _opts, _context) do
    Ash.Changeset.before_transaction(changeset, fn changeset ->
      machine = changeset.data

      case RegentSprites.checkpoint(machine.name, "baseline #{machine.id}") do
        {:ok, checkpoint} ->
          changeset
          |> Ash.Changeset.force_change_attribute(:baseline_checkpoint_id, checkpoint.id)
          |> put_detail(%{checkpoint_id: checkpoint.id, comment: checkpoint.comment})

        {:error, error} ->
          Ash.Changeset.add_error(changeset, error)
      end
    end)
  end
end
