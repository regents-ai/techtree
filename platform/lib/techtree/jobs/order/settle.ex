defmodule Techtree.Jobs.Order.Settle do
  @moduledoc """
  Moves a quoted order on from the deposits saved with its reference, inside
  the payment reader's transaction that saved them (`Techtree.Jobs.Reader`):
  paid once everything deposited reaches the quote; expired once the reading
  has passed a block made at `passed_at`, after the quote's expiry, with too
  little paid. Paying wins: a deposit saved in the same stretch pays. More than
  the quote, or less, is recorded as it is.

  The order is saved only while it is still quoted: the update is not atomic,
  so this filter is part of its `UPDATE`, and an order cancelled meanwhile
  makes the reader's stretch fail, to be read again.
  """

  use Ash.Resource.Change

  require Ash.Expr

  alias Techtree.Jobs.Payment

  @impl true
  def change(changeset, _opts, _context) do
    changeset
    |> Ash.Changeset.filter(Ash.Expr.expr(state == :quoted))
    |> Ash.Changeset.before_action(&settle/1)
  end

  defp settle(changeset) do
    order = changeset.data
    passed_at = Ash.Changeset.get_argument(changeset, :passed_at)

    # The reader's own sum, inside its transaction; no caller reaches it.
    case Ash.load(order, :received, authorize?: false) do
      {:ok, %{received: received}} ->
        case Payment.outcome(order.quote_amount, received, ran_out?(order, passed_at)) do
          :paid -> reach(changeset, :paid, :paid_at)
          :expired -> reach(changeset, :expired, :expired_at)
          :quoted -> changeset
        end

      {:error, error} ->
        Ash.Changeset.add_error(changeset, error)
    end
  end

  defp ran_out?(_order, nil), do: false
  defp ran_out?(order, passed_at), do: DateTime.after?(passed_at, order.quote_expires_at)

  defp reach(changeset, state, at) do
    changeset
    |> AshStateMachine.transition_state(state)
    |> Ash.Changeset.force_change_attribute(at, DateTime.utc_now())
  end
end
