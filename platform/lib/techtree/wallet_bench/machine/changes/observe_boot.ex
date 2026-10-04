defmodule Techtree.WalletBench.Machine.Changes.ObserveBoot do
  @moduledoc """
  Notes the restored machine's boot id and when it was seen, so readiness can
  tell whether the machine restarted in between.
  """

  use Ash.Resource.Change

  import Techtree.WalletBench.Machine.Changes.RecordEvent, only: [put_detail: 2]

  @impl true
  def change(changeset, _opts, _context) do
    Ash.Changeset.before_transaction(changeset, fn changeset ->
      case boot_id(changeset.data.name) do
        {:ok, boot_id} ->
          changeset
          |> Ash.Changeset.force_change_attributes(%{
            boot_id: boot_id,
            boot_seen_at: DateTime.utc_now()
          })
          |> put_detail(%{boot_id: boot_id})

        {:error, error} ->
          Ash.Changeset.add_error(changeset, error)
      end
    end)
  end

  @doc "The machine's current boot id."
  @spec boot_id(String.t()) :: {:ok, String.t()} | {:error, RegentSprites.Error.t()}
  def boot_id(name) do
    with {:ok, content} <- RegentSprites.read_file(name, "/proc/sys/kernel/random/boot_id") do
      {:ok, String.trim(content)}
    end
  end
end
