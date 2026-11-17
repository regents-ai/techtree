defmodule Techtree.Jobs.Order.SetQuote do
  @moduledoc """
  Gives a quoted order its payment reference: 32 fresh random bytes
  (`Techtree.Jobs.Payment.reference/0`), made as the quote is set.
  """

  use Ash.Resource.Change

  alias Techtree.Jobs.Payment

  @impl true
  def change(changeset, _opts, _context),
    do: Ash.Changeset.force_change_attribute(changeset, :payment_reference, Payment.reference())

  @impl true
  def atomic(_changeset, _opts, _context),
    do: {:atomic, %{payment_reference: Payment.reference()}}
end
