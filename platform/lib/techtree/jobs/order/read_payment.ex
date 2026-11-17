defmodule Techtree.Jobs.Order.ReadPayment do
  @moduledoc """
  Reads an order's new deposits from Base and records them, then moves a quoted
  order on: paid once everything deposited reaches the quote, expired once the
  quote has run out with too little.

  Base is read before the transaction opens. One read covers the blocks from
  the first one not read yet up to the newest block `confirmations` deep, at
  most `stretch_blocks` of them (`Techtree.Jobs.Payment.stretch/4`), so every
  deposit read already counts. The deposits are saved once each, by
  transaction and log, whoever sent them: a deposit from any wallet with the
  order's reference pays it. More than the quote, or less, is recorded as it is.

  A quote has run out only once the reading has reached a block made after its
  expiry, so a payment made in time is never missed. An expired order's later
  deposits are recorded and change nothing.

  The order is saved only if no other read moved it on meanwhile. A node that
  cannot be read logs one warning and tries again in a minute; a log that is
  not a deposit fails the read, to retry.
  """

  use Ash.Resource.Change

  require Ash.Expr
  require Logger

  alias AshOban.Errors.SnoozeJob
  alias Techtree.Actors.System
  alias Techtree.Jobs.{Deposit, Payment, Staking}

  @impl true
  def change(changeset, _opts, _context) do
    %{next_block: next_block, state: state} = changeset.data

    changeset
    |> Ash.Changeset.filter(Ash.Expr.expr(next_block == ^next_block and state == ^state))
    |> Ash.Changeset.before_transaction(&read/1)
    |> Ash.Changeset.before_action(&record/1)
  end

  defp read(changeset) do
    order = changeset.data
    settings = Payment.config()

    with {:ok, head} <- Staking.head(),
         stretch =
           Payment.stretch(
             order.next_block,
             head,
             settings[:confirmations],
             settings[:stretch_blocks]
           ),
         {:ok, deposits} <- deposits(order.payment_reference, stretch),
         {:ok, expiry_passed?} <- expiry_passed?(order, stretch) do
      Ash.Changeset.set_context(changeset, %{
        payment_read: %{stretch: stretch, deposits: deposits, expiry_passed?: expiry_passed?}
      })
    else
      {:error, {:malformed_log, _log} = reason} ->
        Ash.Changeset.add_error(changeset, "a deposit could not be read: #{inspect(reason)}")

      {:error, reason} ->
        Logger.warning("Base could not be read for job order #{order.id}: #{inspect(reason)}")
        Ash.Changeset.add_error(changeset, SnoozeJob.exception(snooze_for: 60))
    end
  end

  defp deposits(_reference, %{from: from, to: to}) when to < from, do: {:ok, []}
  defp deposits(reference, %{from: from, to: to}), do: Staking.deposits(reference, from, to)

  # Only a quoted order can run out, and only once every block up to one made
  # after its expiry has been read.
  defp expiry_passed?(%{state: :quoted} = order, %{to: frontier, frontier: frontier}) do
    if DateTime.compare(DateTime.utc_now(), order.quote_expires_at) == :lt do
      {:ok, false}
    else
      with {:ok, time} <- Staking.block_time(frontier),
           do: {:ok, time > DateTime.to_unix(order.quote_expires_at)}
    end
  end

  defp expiry_passed?(_order, _stretch), do: {:ok, false}

  defp record(changeset) do
    order = changeset.data

    %{stretch: stretch, deposits: deposits, expiry_passed?: expiry_passed?} =
      changeset.context.payment_read

    with %Ash.BulkResult{status: :success} <-
           Ash.bulk_create(
             Enum.map(deposits, &Map.put(&1, :order_id, order.id)),
             Deposit,
             :record,
             actor: %System{},
             return_errors?: true
           ),
         # The trigger's own read of its order, which no caller reaches.
         {:ok, %{received: received}} <- Ash.load(order, :received, authorize?: false) do
      changeset
      |> Ash.Changeset.force_change_attribute(:next_block, max(order.next_block, stretch.to + 1))
      |> move_on(order, Payment.outcome(order.quote_amount, received, expiry_passed?))
    else
      %Ash.BulkResult{errors: errors} -> Ash.Changeset.add_error(changeset, errors)
      {:error, error} -> Ash.Changeset.add_error(changeset, error)
    end
  end

  defp move_on(changeset, %{state: :quoted}, :paid), do: reach(changeset, :paid, :paid_at)

  defp move_on(changeset, %{state: :quoted}, :expired),
    do: reach(changeset, :expired, :expired_at)

  defp move_on(changeset, _order, _outcome), do: changeset

  defp reach(changeset, state, at) do
    changeset
    |> AshStateMachine.transition_state(state)
    |> Ash.Changeset.force_change_attribute(at, DateTime.utc_now())
  end
end
