defmodule Techtree.Watchdog.Host.CheckOwnership do
  @moduledoc """
  Reads a host's published proof and records what it found, outside any
  transaction. A proof that matches makes the host proven; one that does not
  leaves a first check unproven and drops a previously proven host to revoked,
  so a host that stops publishing its proof stops counting as owned.

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

        {:error, _reason} ->
          Ash.Changeset.force_change_attributes(changeset, %{
            ownership_state: failed_state(changeset.data.ownership_state),
            last_checked_at: now
          })
      end
    end)
  end

  defp failed_state(:verified), do: :revoked
  defp failed_state(_other), do: :unverified
end
