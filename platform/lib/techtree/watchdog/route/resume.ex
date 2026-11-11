defmodule Techtree.Watchdog.Route.Resume do
  @moduledoc """
  Turns a paused route back on, but only under a proven host, so a route can
  never be active while its host is unproven.
  """

  use Ash.Resource.Change

  @impl true
  def change(changeset, _opts, _context) do
    Ash.Changeset.before_action(changeset, fn changeset ->
      # The update policy has already proven the actor owns this route, and so
      # its host; loading the host only to read its own proof state is not a
      # second access decision, so it is read without re-authorizing.
      case Ash.load(changeset.data, :host, authorize?: false) do
        {:ok, %{host: %{ownership_state: :verified}}} ->
          Ash.Changeset.force_change_attribute(changeset, :state, :active)

        _unverified_host ->
          Ash.Changeset.add_error(changeset,
            field: :state,
            message: "can't turn on an address until its site is proven"
          )
      end
    end)
  end
end
