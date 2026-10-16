defmodule Techtree.WalletBench.Machine.Changes.ConfirmReady do
  @moduledoc """
  Readiness: once 30 seconds have gone by since the boot id was noted, the
  machine is ready when the boot id is unchanged, a file of random bytes written
  to it reads back exactly, Sprites reports the image versions it was created
  with, the tested account cannot read `/work`, use sudo, list the checkpoints or
  reach the management socket (`readiness.sh`, which locks them and empties
  `/tmp` first: a restore leaves that disk as the last attempt left it), and the
  harness reports the version the baseline recorded. Any check that does not
  hold, or a readiness answer that is not exactly the four account checks as
  true or false and a harness version, marks the machine failed with that
  reason, at once and without a retry (plan D18). A call to Sprites that fails
  is an error, which the job retries.
  """

  use Ash.Resource.Change

  import Techtree.WalletBench.Machine.Changes.RecordEvent, only: [put_detail: 2]

  alias Techtree.WalletBench.Machine.Changes.ObserveBoot
  alias Techtree.WalletBench.Remote

  @settle_seconds 30
  @upload_path "/tmp/techtree-readiness"

  @impl true
  def change(changeset, _opts, _context) do
    Ash.Changeset.before_transaction(changeset, fn changeset ->
      machine = changeset.data
      waited = DateTime.diff(DateTime.utc_now(), machine.boot_seen_at)

      if waited < @settle_seconds do
        Ash.Changeset.add_error(
          changeset,
          AshOban.Errors.SnoozeJob.exception(snooze_for: @settle_seconds - waited)
        )
      else
        apply_checks(changeset, checks(machine))
      end
    end)
  end

  defp apply_checks(changeset, {:ok, detail}) do
    changeset
    |> Ash.Changeset.force_change_attribute(:state, :ready)
    |> put_detail(detail)
  end

  defp apply_checks(changeset, {:failed, reason, detail}) do
    changeset
    |> Ash.Changeset.force_change_attributes(%{state: :failed, failure: reason})
    |> put_detail(Map.put(detail, :failure, reason))
  end

  defp apply_checks(changeset, {:error, error}), do: Ash.Changeset.add_error(changeset, error)

  defp checks(machine) do
    bytes = :crypto.strong_rand_bytes(32)

    with {:ok, boot_id} <- ObserveBoot.boot_id(machine.name),
         :ok <- RegentSprites.write_file(machine.name, @upload_path, bytes),
         {:ok, read_back} <- RegentSprites.read_file(machine.name, @upload_path),
         {:ok, sprite} <- RegentSprites.get(machine.name),
         {:ok, account, harness_version} <- readiness(machine) do
      detail = %{
        boot_id: boot_id,
        upload_round_trip: read_back == bytes,
        sprite_version: sprite.version,
        environment_version: sprite.environment_version,
        account: account,
        harness_version: harness_version
      }

      verdict(machine, detail, read_back == bytes)
    end
  end

  # The answer readiness.sh gives: exactly the four account checks, each true or
  # false, and the harness version. Any other answer fails the machine.
  defp readiness(machine) do
    case Remote.json(machine.name, ["bash", "/work/bin/machine/readiness.sh", machine.harness_id]) do
      {:ok,
       %{
         "account" =>
           %{
             "work_readable" => work_readable,
             "sudo" => sudo,
             "checkpoints_listable" => checkpoints_listable,
             "socket_reachable" => socket_reachable
           } = account,
         "harness_version" => harness_version
       }}
      when is_boolean(work_readable) and is_boolean(sudo) and is_boolean(checkpoints_listable) and
             is_boolean(socket_reachable) and is_binary(harness_version) ->
        {:ok, account, harness_version}

      {:ok, _unrecognised} ->
        {:failed, "The readiness check printed an answer it does not give.", %{}}

      {:error, error} ->
        {:error, error}
    end
  end

  defp verdict(machine, detail, round_trip?) do
    reachable = for {check, true} <- detail.account, do: check

    cond do
      detail.boot_id != machine.boot_id ->
        {:failed, "The machine restarted after its restore.", detail}

      not round_trip? ->
        {:failed, "A file written to the machine did not read back the same.", detail}

      {detail.sprite_version, detail.environment_version} !=
          {machine.sprite_version, machine.environment_version} ->
        {:failed, "The machine's image changed since it was created.", detail}

      reachable != [] ->
        {:failed, "The tested account can reach the bench: #{Enum.join(reachable, ", ")}.",
         detail}

      detail.harness_version != machine.manifest["harness_version"] ->
        {:failed, "The harness version changed since the baseline was built.", detail}

      true ->
        {:ok, detail}
    end
  end
end
