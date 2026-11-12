defmodule Techtree.Messages.Message.SpendAllowance do
  @moduledoc """
  Holds each sender to the `:message` allowance in `Techtree.Limits`, and the
  client address the message came from to `:message_address`. The caller passes
  that address as `context: %{client_key: key}` (`TechtreeWeb.ClientAddress`).
  A message counts when it is saved, not while it is typed, so checking a draft
  never uses the allowance.
  """

  use Ash.Resource.Change

  alias Techtree.Limits

  @quickly "You're going quickly. Wait a moment and try again."

  @impl true
  def change(changeset, _opts, %{actor: actor}) do
    Ash.Changeset.before_action(changeset, fn %{context: %{client_key: key}} = changeset ->
      if Limits.spend(:message, Limits.writer(actor)) == :ok and
           Limits.spend(:message_address, key) == :ok,
         do: changeset,
         else: Ash.Changeset.add_error(changeset, field: :body, message: @quickly)
    end)
  end
end
