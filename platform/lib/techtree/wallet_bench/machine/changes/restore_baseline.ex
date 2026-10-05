defmodule Techtree.WalletBench.Machine.Changes.RestoreBaseline do
  @moduledoc """
  Puts the machine's disk back to its baseline.

  A new baseline is restored no sooner than a minute after its checkpoint (an
  Oban snooze). Sprites finishes a checkpoint in the background for a short
  while, and a restore made during that time can fail with "file exists";
  after that the machine can neither checkpoint nor restore again (seen on 5
  October in one of five immediate restores; none of three made 45 seconds
  later failed). Such a machine fails after its retries and is retired.
  """

  use Ash.Resource.Change

  import Techtree.WalletBench.Machine.Changes.RecordEvent, only: [put_detail: 2]

  @settle_seconds 60

  @impl true
  def change(changeset, _opts, _context) do
    Ash.Changeset.before_transaction(changeset, fn changeset ->
      machine = changeset.data

      case settle_left(machine) do
        0 ->
          restore(changeset, machine)

        seconds ->
          Ash.Changeset.add_error(
            changeset,
            AshOban.Errors.SnoozeJob.exception(snooze_for: seconds)
          )
      end
    end)
  end

  defp settle_left(%{state: :checkpointed, updated_at: checkpointed_at}),
    do: max(@settle_seconds - DateTime.diff(DateTime.utc_now(), checkpointed_at), 0)

  defp settle_left(_resetting), do: 0

  defp restore(changeset, machine) do
    case RegentSprites.restore(machine.name, machine.baseline_checkpoint_id) do
      :ok -> put_detail(changeset, %{checkpoint_id: machine.baseline_checkpoint_id})
      {:error, error} -> Ash.Changeset.add_error(changeset, error)
    end
  end
end
