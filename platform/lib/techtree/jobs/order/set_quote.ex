defmodule Techtree.Jobs.Order.SetQuote do
  @moduledoc """
  Gives a quoted order its payment reference and the block its payments are
  read from: the newest block as the quote is set, read before the order is
  saved. No deposit can carry a reference before it exists, so nothing earlier
  needs reading. A quote set while Base cannot be read is refused, to be set
  again.
  """

  use Ash.Resource.Change

  alias Techtree.Jobs.{Payment, Staking}

  @impl true
  def change(changeset, _opts, _context) do
    changeset
    |> Ash.Changeset.force_change_attribute(:payment_reference, Payment.reference())
    |> Ash.Changeset.before_transaction(fn changeset ->
      case Staking.head() do
        {:ok, head} ->
          Ash.Changeset.force_change_attribute(changeset, :next_block, head)

        {:error, reason} ->
          Ash.Changeset.add_error(changeset, "Base could not be read: #{inspect(reason)}")
      end
    end)
  end
end
