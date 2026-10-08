defmodule Techtree.WalletBench.Attempt.Changes.SendFunding do
  @moduledoc """
  Broadcasts the attempt's signed funding sends and reads their receipts on
  Base (`Techtree.WalletBench.Funding.receipts/1`), waiting (an Oban snooze)
  while one is still pending.

  - Both confirmed: the attempt is `testing` again, and T3 is queued,
    continuing the wallet test's conversation.
  - One reverted: the attempt stops, with the send's hash.
  - One still pending ten minutes after it was signed: it becomes `unknown`,
    which pauses all funding, and the attempt stops.

  Each receipt is written to its payment in the same transaction.
  """

  use Ash.Resource.Change

  import Techtree.WalletBench.Attempt.Changes.RecordEvent, only: [put_detail: 2]

  alias Techtree.WalletBench.{Catalog, Funding, Turn}

  @wait_seconds 10
  @deadline_seconds 600

  @impl true
  def change(changeset, _opts, _context) do
    Ash.Changeset.before_transaction(changeset, fn changeset ->
      attempt = changeset.data

      with {:ok, payments} <- Techtree.WalletBench.list_payments(attempt.id),
           {:ok, receipts} <- Funding.receipts(Enum.filter(payments, &(&1.state == :signed))) do
        settle(changeset, receipts)
      else
        {:error, error} -> Ash.Changeset.add_error(changeset, error)
      end
    end)
  end

  defp settle(changeset, receipts) do
    pending = for {payment, :pending} <- receipts, do: payment
    reverted = for {payment, {:reverted, _block}} <- receipts, do: payment
    late = Enum.filter(pending, &late?/1)

    cond do
      reverted != [] ->
        stop(changeset, receipts, "A funding send failed on Base: #{hd(reverted).hash}.")

      late != [] ->
        stop(
          changeset,
          receipts,
          "No receipt for the funding send #{hd(late).hash} came in ten minutes; its outcome is unknown and funding is paused."
        )

      pending != [] ->
        Ash.Changeset.add_error(
          changeset,
          AshOban.Errors.SnoozeJob.exception(snooze_for: @wait_seconds)
        )

      true ->
        changeset
        |> Ash.Changeset.force_change_attribute(:state, :testing)
        |> put_detail(%{sends: Enum.map(receipts, &receipt/1)})
        |> Ash.Changeset.after_action(fn _changeset, attempt -> funded(attempt, receipts) end)
    end
  end

  defp funded(attempt, receipts) do
    with {:ok, attempt} <- write(attempt, receipts), do: queue_t3(attempt)
  end

  defp stop(changeset, receipts, reason) do
    changeset
    |> Ash.Changeset.force_change_attributes(%{state: :revoking, failure: reason})
    |> put_detail(%{failure: reason, sends: Enum.map(receipts, &receipt/1)})
    |> Ash.Changeset.after_action(fn _changeset, attempt -> write(attempt, receipts) end)
  end

  defp late?(payment),
    do: DateTime.diff(DateTime.utc_now(), payment.inserted_at) > @deadline_seconds

  defp receipt({payment, {outcome, block}}),
    do: %{hash: payment.hash, outcome: outcome, block: block}

  defp receipt({payment, :pending}), do: %{hash: payment.hash, outcome: :pending}

  defp write(attempt, receipts) do
    Enum.reduce_while(receipts, {:ok, attempt}, fn receipt, {:ok, attempt} ->
      case update(receipt) do
        {:ok, _payment} -> {:cont, {:ok, attempt}}
        {:error, error} -> {:halt, {:error, error}}
      end
    end)
  end

  defp update({payment, {:confirmed, block}}), do: update(payment, :confirm, %{block: block})
  defp update({payment, {:reverted, block}}), do: update(payment, :revert, %{block: block})
  defp update({payment, :pending}), do: update(payment, :lose, %{})

  defp update(payment, action, params) do
    payment
    |> Ash.Changeset.for_update(action, params)
    # Payments have no public writer; the attempt's own funding step is one of two.
    |> Ash.update(authorize?: false)
  end

  defp queue_t3(attempt) do
    attempt = Ash.load!(attempt, :turns)
    wallet_turn = attempt.turns |> Enum.filter(&(&1.test in [:T2, :T2_signature])) |> List.last()

    Turn
    |> Ash.Changeset.for_create(:queue, %{
      attempt_id: attempt.id,
      test: :T3,
      prompt: Catalog.prompt(:T3, attempt.harness_id, attempt.wallet_id, nil),
      resume_session_id: wallet_turn.session_id
    })
    # Turns have no public writer; the attempt's own step queues T3.
    |> Ash.create(authorize?: false)
    |> case do
      {:ok, _turn} -> {:ok, attempt}
      {:error, error} -> {:error, error}
    end
  end
end
