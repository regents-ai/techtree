defmodule Techtree.WalletBench.Payment.Changes.Settle do
  @moduledoc """
  Settles an unknown send from Base itself (`Techtree.WalletBench.Funding.settled/1`),
  read before the transaction opens: its receipt makes it `confirmed` or
  `reverted` at that block, and with no receipt it is `replaced` only once the
  funder's nonce at the latest block has passed it. While that nonce is unused,
  the stored bytes can still land, so the send stays unknown and funding stays
  paused.
  """

  use Ash.Resource.Change

  alias Techtree.WalletBench.Funding

  @impl true
  def change(changeset, _opts, _context) do
    Ash.Changeset.before_transaction(changeset, fn changeset ->
      case Funding.settled(changeset.data) do
        {:ok, {state, block}} ->
          Ash.Changeset.force_change_attributes(changeset, %{state: state, block: block})

        {:ok, :replaced} ->
          Ash.Changeset.force_change_attribute(changeset, :state, :replaced)

        {:error, error} ->
          Ash.Changeset.add_error(changeset, error)
      end
    end)
  end
end
