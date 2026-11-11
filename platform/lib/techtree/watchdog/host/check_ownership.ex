defmodule Techtree.Watchdog.Host.CheckOwnership do
  @moduledoc """
  Reads a host's published proof and records what it found, outside any
  transaction. A proof that matches makes the host proven. A proof that is
  positively missing or different leaves a first check unproven and drops a
  previously proven host to revoked, so a host that stops publishing its proof
  stops counting as owned. A check that could not read the proof at all (a
  network error, a timeout, a failed lookup) records nothing and fails the
  action, so the job retries and a proven host stays proven.

  The only request this makes is the ownership check itself
  (`Techtree.Watchdog.Ownership`); it reaches nothing else of the customer's.
  """

  use Ash.Resource.Change

  alias Techtree.Watchdog.Ownership

  @impl true
  def change(changeset, _opts, _context) do
    Ash.Changeset.before_action(changeset, fn changeset ->
      now = DateTime.utc_now(:second)

      case Ownership.verify(changeset.data) do
        :ok ->
          Ash.Changeset.force_change_attributes(changeset, %{
            ownership_state: :verified,
            verified_at: now,
            last_checked_at: now
          })

        {:error, :proof_missing} ->
          Ash.Changeset.force_change_attributes(changeset, %{
            ownership_state: failed_state(changeset.data.ownership_state),
            last_checked_at: now
          })

        {:error, reason} ->
          Ash.Changeset.add_error(changeset, "the proof could not be read: #{inspect(reason)}")
      end
    end)
  end

  defp failed_state(:verified), do: :revoked
  defp failed_state(_other), do: :unverified
end
