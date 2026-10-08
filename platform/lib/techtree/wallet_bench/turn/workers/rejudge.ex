defmodule Techtree.WalletBench.Turn.Workers.Rejudge do
  @moduledoc """
  Rules again, with the nine checks of the current review guides, on every
  judged turn of one attempt that still carries an older ruling (Sean, WB-9 a).

  The turns go in the order they ran, because a second try's evidence includes
  the first try's ruling. Each job stops for good once the nine-check rulings
  together have cost `cap_usd`; jobs then still queued stop at their first turn.
  A turn that already has nine checks is skipped, so a job that runs twice
  pays for nothing twice.

  Queued by an operator from a console with `enqueue_all/1`.
  """

  use Oban.Worker,
    queue: :wallet_bench_judge,
    max_attempts: 5,
    unique: [keys: [:attempt_id], period: :infinity, states: :incomplete]

  require Ash.Query

  alias Techtree.WalletBench.Turn

  @doc """
  Queues one job per attempt with an older ruling; returns how many were new.
  Each job is inserted alone, because `Oban.insert_all/1` skips the unique
  check in Oban's basic engine.
  """
  @spec enqueue_all(String.t()) :: non_neg_integer()
  def enqueue_all(cap_usd) do
    Turn
    |> Ash.Query.filter(state == :judged and not nine_checks?)
    |> Ash.Query.select([:attempt_id])
    |> Ash.read!()
    |> Enum.map(& &1.attempt_id)
    |> Enum.uniq()
    |> Enum.map(&Oban.insert!(new(%{attempt_id: &1, cap_usd: cap_usd})))
    |> Enum.count(&(not &1.conflict?))
  end

  @impl Oban.Worker
  def perform(%Oban.Job{args: %{"attempt_id" => attempt_id, "cap_usd" => cap_usd}}) do
    Turn
    |> Ash.Query.filter(attempt_id == ^attempt_id and state == :judged and not nine_checks?)
    |> Ash.Query.sort(inserted_at: :asc)
    |> Ash.read!()
    |> Enum.reduce_while(:ok, fn turn, :ok -> rejudge(turn, cap_usd) end)
  end

  defp rejudge(turn, cap_usd) do
    if Decimal.compare(spent(), Decimal.new(cap_usd)) == :lt do
      # Turns have no public writer; an operator queued this re-judge, as the
      # domain's other console actions are run with policies skipped.
      case Techtree.WalletBench.rejudge_turn(turn, authorize?: false) do
        {:ok, _turn} -> {:cont, :ok}
        {:error, error} -> {:halt, {:error, error}}
      end
    else
      {:halt, {:cancel, "the re-judge has cost #{cap_usd} USD, its cap"}}
    end
  end

  defp spent do
    Turn
    |> Ash.Query.filter(nine_checks?)
    |> Ash.sum!(:judge_cost_usd)
    |> Kernel.||(Decimal.new(0))
  end
end
