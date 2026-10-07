defmodule Techtree.WalletBench.Machine.Changes.BuildBaseline do
  @moduledoc """
  Builds the machine's baseline: sends the recipe pack and starts
  `baseline.sh` as a background job, then waits for it (an Oban snooze) until it
  ends. A build that ends with exit code 0 leaves the machine `built`, with the
  baseline manifest and the digest of the scripts it carries. A build that fails
  or is lost marks the machine failed at once, with the end of its log
  blanked of secret patterns; a repeat would only build the same thing again.
  """

  use Ash.Resource.Change

  import Techtree.WalletBench.Machine.Changes.RecordEvent, only: [put_detail: 2]

  alias Techtree.WalletBench.{Blank, Catalog, Remote}

  @job "baseline"
  @wait_seconds 30

  @impl true
  def change(changeset, _opts, _context) do
    Ash.Changeset.before_transaction(changeset, fn changeset ->
      machine = changeset.data

      case Remote.job_status(machine.name, @job) do
        {:ok, :missing} -> start(changeset, machine)
        {:ok, :running} -> wait(changeset)
        {:ok, {:exit, 0}} -> built(changeset, machine)
        {:ok, {:exit, code}} -> failed(changeset, machine, "ended with exit code #{code}")
        {:ok, :lost} -> failed(changeset, machine, "stopped without finishing")
        {:error, error} -> Ash.Changeset.add_error(changeset, error)
      end
    end)
  end

  defp start(changeset, machine) do
    {pack, _digest} = Catalog.recipe_pack()
    script = ["bash", "/work/bin/machine/baseline.sh", machine.harness_id]

    with :ok <- Remote.upload_pack(machine.name, pack),
         :ok <- Remote.start_job(machine.name, @job, script) do
      wait(changeset)
    else
      {:error, error} -> Ash.Changeset.add_error(changeset, error)
    end
  end

  defp wait(changeset),
    do:
      Ash.Changeset.add_error(
        changeset,
        AshOban.Errors.SnoozeJob.exception(snooze_for: @wait_seconds)
      )

  defp built(changeset, machine) do
    with {:ok, manifest} <- Remote.json(machine.name, ["cat", "/work/baseline/manifest.json"]),
         {:ok, digest} <- Remote.recipe_digest(machine.name) do
      changeset
      |> Ash.Changeset.force_change_attributes(%{
        state: :built,
        manifest: manifest,
        recipe_digest: digest
      })
      |> put_detail(%{manifest: manifest, recipe_digest: digest})
    else
      {:error, error} -> Ash.Changeset.add_error(changeset, error)
    end
  end

  defp failed(changeset, machine, how) do
    case Remote.job_log_tail(machine.name, @job) do
      {:ok, log} ->
        reason = "The baseline build #{how}."

        changeset
        |> Ash.Changeset.force_change_attributes(%{state: :failed, failure: reason})
        |> put_detail(%{failure: reason, log_tail: Blank.blank(log, [])})

      {:error, error} ->
        Ash.Changeset.add_error(changeset, error)
    end
  end
end
