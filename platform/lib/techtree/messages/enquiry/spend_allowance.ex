defmodule Techtree.Messages.Enquiry.SpendAllowance do
  @moduledoc """
  Holds the client address an enquiry comes from to the `:enquiry_address`
  allowance in `Techtree.Limits`. The caller passes the address's key as
  `context: %{client_key: key}` (`TechtreeWeb.ClientAddress.client_key/1`); the
  key is never saved. An enquiry counts when it is saved, not while it is typed,
  so checking a draft never uses the allowance. A refusal is the whole form's,
  not one field's.
  """

  use Ash.Resource.Change

  alias Ash.Error.Changes.InvalidChanges
  alias Techtree.Limits

  @busy "You've sent several in the last hour. Try again later, or email build@regents.sh."

  @impl true
  def change(changeset, _opts, _context) do
    Ash.Changeset.before_action(changeset, fn %{context: %{client_key: key}} = changeset ->
      case Limits.spend(:enquiry_address, key) do
        :ok ->
          changeset

        :limited ->
          Ash.Changeset.add_error(changeset, InvalidChanges.exception(fields: [], message: @busy))
      end
    end)
  end
end
