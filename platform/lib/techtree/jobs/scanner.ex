defmodule Techtree.Jobs.Scanner do
  @moduledoc """
  One pass over the job payments one staking contract received on one chain,
  read at the latest block (`Techtree.Jobs.Staking`), from where the contract's
  cursor stands (`Techtree.Jobs.Cursor`) up to the head this pass read.

  The cursor opens at the head the first time the contract's reading job runs
  (`Techtree.Jobs.ReadPayments`), so a deposit made before then is never read.
  Each stretch is one log search, from 300 blocks before the cursor (one
  minute of Base) to at most 10,000 blocks on, never above the head; a stretch
  the node refuses is asked for in halves, down to one block. A stretch's new
  deposits, the orders they move on and the cursor's move commit in one
  transaction, and the cursor moves only from where this pass found it.

  Every job payment is saved, whoever sent it and whatever reference it
  carries: one whose reference matches no order is saved with none. In the same
  transaction, each quoted order a new deposit carries the reference of is
  settled (`Techtree.Jobs.Order.Settle`), and paid once its deposits reach its
  quote. A quote runs out only in the stretch that reaches the head, when the
  head's block was made after the quote's expiry, with too little paid.

  A transaction's deposits are saved by the first stretch that reads it and
  kept as first saved. Each saved transaction is checked once, by the stretch
  that reads its block for the last time: when its logs no longer match its
  saved rows (moved to another block, in a block whose hash changed, changed,
  or gone), that is one warning naming the contract and the transaction, and
  the pass reads on. A log that does not read as a deposit, or one block the
  node refuses, ends the pass before its stretch is saved, to be read again.

  A pass that reaches the head reports `[:techtree, :indexer, :lag]` with
  `blocks`, the head less the last block read, under the indexer name
  `"job_payments"` and the `chain_id`.
  """

  require Logger

  alias Techtree.Actors.System
  alias Techtree.Jobs
  alias Techtree.Jobs.{Cursor, Deposit, Order, Staking}

  # On Base, the last minute of blocks, read again by every stretch, and the
  # most blocks one search asks for.
  @reread 300
  @stretch 10_000
  @indexer "job_payments"
  @system %System{}

  @type reader :: %{chain_id: pos_integer(), contract: String.t()}

  @doc """
  Reads `reader`'s contract on from its cursor up to the head. `:ok` once the
  cursor is past the head this pass read, or when another pass moved it first;
  `{:error, reason}` when the node or the database failed, the cursor then
  standing after the last stretch saved.
  """
  @spec pass(reader()) :: :ok | {:error, term()}
  def pass(reader) do
    with {:ok, head} <- Staking.head(),
         {:ok, cursor} <- cursor(reader, head),
         do: forward(reader, cursor, head)
  end

  # The first pass opens the cursor at the head it read.
  defp cursor(reader, head) do
    case Jobs.get_cursor(reader.chain_id, reader.contract, actor: @system) do
      {:ok, nil} ->
        Jobs.open_cursor(
          %{chain_id: reader.chain_id, contract: reader.contract, next_block: head.number},
          actor: @system
        )

      answer ->
        answer
    end
  end

  # A node that is behind makes a shorter pass, never missing history.
  defp forward(reader, %{next_block: next} = cursor, %{number: number} = head)
       when next > number,
       do: lag(reader, cursor, head)

  defp forward(reader, cursor, head) do
    from = max(cursor.next_block - @reread, 0)
    to = min(head.number, from + @stretch - 1)

    with {:ok, logs} <- logs(reader.contract, from, to),
         {:ok, read} <- rows(reader, logs),
         {:ok, saved} <-
           Jobs.seen_deposits(
             reader.chain_id,
             reader.contract,
             from,
             cursor.next_block - 1,
             read |> Enum.map(& &1.transaction_hash) |> Enum.uniq(),
             actor: @system
           ),
         {fresh, moved} = compare(read, saved, from, to - @reread),
         {:ok, cursor} <- commit(cursor, fresh, to, head) do
      Enum.each(moved, &warn(reader, &1))
      forward(reader, cursor, head)
    else
      :superseded -> :ok
      {:error, reason} -> {:error, reason}
    end
  end

  # A range the node refuses is asked for in halves, down to one block; one
  # block it still refuses ends the pass.
  defp logs(contract, from, to) do
    case Staking.logs(contract, from, to) do
      {:error, {:refused, _error}} when from < to ->
        middle = div(from + to, 2)

        with {:ok, low} <- logs(contract, from, middle),
             {:ok, high} <- logs(contract, middle + 1, to),
             do: {:ok, low ++ high}

      answer ->
        answer
    end
  end

  # Each job payment as its row, in chain order; a log that does not read as a
  # deposit ends the pass, naming its transaction.
  defp rows(reader, logs) do
    read = Enum.map(logs, &{&1, Staking.decode(&1, reader.contract)})

    case Enum.find(read, &match?({_log, :error}, &1)) do
      nil ->
        {:ok, for({_log, {:ok, %{} = row}} <- read, do: Map.put(row, :chain_id, reader.chain_id))}

      {log, :error} ->
        {:error, {:unreadable_log, log["transactionHash"]}}
    end
  end

  # The rows of transactions not saved yet, and each saved transaction whose
  # block this stretch reads for the last time (`from` to `last`: the next
  # stretch's search starts after `last`) and whose logs read now differ from
  # its saved rows. A transaction's logs are all in one block.
  defp compare(read, saved, from, last) do
    saved = Enum.group_by(saved, & &1.transaction_hash)
    read_now = Enum.group_by(read, & &1.transaction_hash)
    fresh = Enum.reject(read, &Map.has_key?(saved, &1.transaction_hash))

    moved =
      for {transaction, [%{block_number: block} | _] = rows} <- saved,
          from <= block and block <= last,
          facts(rows) != facts(Map.get(read_now, transaction, [])),
          do: transaction

    {fresh, Enum.sort(moved)}
  end

  # What a transaction's logs say, in a form a saved row and a read one share.
  defp facts(rows) do
    rows
    |> Enum.map(
      &{&1.log_index, &1.block_number, &1.block_hash, &1.contract, &1.depositor, &1.reference,
       Decimal.to_integer(&1.amount)}
    )
    |> Enum.sort()
  end

  # The stretch's new deposits, the orders they move on and the cursor's move
  # to `to + 1` commit together. Once the stretch reaches the head, the head's
  # time is when a quote must have run out by to expire.
  defp commit(cursor, rows, to, head) do
    passed_at = if to == head.number, do: head.timestamp

    Ash.transact([Deposit, Cursor, Order], fn ->
      with :ok <- each(rows, &Jobs.record_deposit(&1, actor: @system)),
           {:ok, cursor} <-
             Jobs.advance_cursor(
               cursor,
               %{
                 from: cursor.next_block,
                 next_block: to + 1,
                 head_block: head.number,
                 head_block_hash: head.hash,
                 observed_at: DateTime.utc_now()
               },
               actor: @system
             ),
           :ok <- settle(rows, passed_at) do
        cursor
      end
    end)
    |> case do
      {:ok, cursor} -> {:ok, cursor}
      {:error, error} -> if stale?(error), do: :superseded, else: {:error, error}
    end
  end

  defp settle([], nil), do: :ok

  defp settle(rows, passed_at) do
    references = rows |> Enum.map(& &1.reference) |> Enum.uniq()

    with {:ok, orders} <- Jobs.due_orders(references, passed_at, actor: @system),
         do: each(orders, &Jobs.settle_order(&1, passed_at, actor: @system))
  end

  defp each(items, action) do
    Enum.reduce_while(items, :ok, fn item, :ok ->
      case action.(item) do
        {:ok, _done} -> {:cont, :ok}
        {:error, error} -> {:halt, {:error, error}}
      end
    end)
  end

  # Another pass moved the cursor first, or an order moved meanwhile: nothing
  # of this stretch is saved, and the next pass reads it from where the cursor
  # stands.
  defp stale?(error),
    do:
      Enum.any?(
        Ash.Error.to_error_class(error).errors,
        &match?(%Ash.Error.Changes.StaleRecord{}, &1)
      )

  defp warn(reader, transaction) do
    Logger.warning(
      "Job payments on #{reader.contract} in transaction #{transaction} no longer match the " <>
        "chain; the rows saved first are kept"
    )
  end

  defp lag(reader, cursor, head) do
    :telemetry.execute(
      [:techtree, :indexer, :lag],
      %{blocks: max(head.number - (cursor.next_block - 1), 0)},
      %{indexer: @indexer, chain_id: reader.chain_id}
    )
  end
end
