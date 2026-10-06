defmodule Techtree.WalletBench.Attempt.Changes.LeaseMachine do
  @moduledoc """
  Takes a ready machine for the attempt's harness whose baseline carries
  today's recipe, inside the attempt's transaction, so two attempts never take
  the same machine. With none ready, the job waits (an Oban snooze) and looks
  again.
  """

  use Ash.Resource.Change

  require Ash.Query

  import Techtree.WalletBench.Attempt.Changes.RecordEvent, only: [put_detail: 2]

  alias Techtree.WalletBench.{Catalog, Machine}

  @wait_seconds 60

  @impl true
  def change(changeset, _opts, _context) do
    Ash.Changeset.before_action(changeset, fn changeset ->
      attempt = changeset.data

      case ready_machine(attempt.harness_id) do
        {:ok, nil} ->
          Ash.Changeset.add_error(
            changeset,
            AshOban.Errors.SnoozeJob.exception(snooze_for: @wait_seconds)
          )

        {:ok, machine} ->
          lease(changeset, machine, attempt)

        {:error, error} ->
          Ash.Changeset.add_error(changeset, error)
      end
    end)
  end

  defp ready_machine(harness_id) do
    digest = Catalog.recipe_digest()

    Machine
    |> Ash.Query.filter(
      state == :ready and harness_id == ^harness_id and recipe_digest == ^digest
    )
    |> Ash.Query.lock("FOR UPDATE SKIP LOCKED")
    |> Ash.Query.limit(1)
    # The attempt's own step, inside its authorized action.
    |> Ash.read_one(authorize?: false)
  end

  defp lease(changeset, machine, attempt) do
    machine
    |> Ash.Changeset.for_update(:lease, %{attempt_id: attempt.id})
    # Machines have no public writer; the attempt's own lease job is one of the few.
    |> Ash.update(authorize?: false)
    |> case do
      {:ok, machine} ->
        changeset
        |> Ash.Changeset.force_change_attribute(:machine_id, machine.id)
        |> put_detail(%{
          machine: machine.name,
          harness_version: machine.manifest["harness_version"]
        })

      {:error, error} ->
        Ash.Changeset.add_error(changeset, error)
    end
  end
end
