defmodule Techtree.ErrorPruner do
  @moduledoc """
  Clears saved errors once a day: every occurrence older than a week, and every
  error not seen for a week, whatever its status. ErrorTracker's own pruner only
  clears resolved errors, so a fault that keeps happening would otherwise grow
  the error tables without end.
  """
  use Oban.Worker, queue: :default, max_attempts: 3

  import Ecto.Query

  alias ErrorTracker.{Error, Occurrence}
  alias Techtree.Repo

  @batch 5_000

  @impl Oban.Worker
  def perform(_job) do
    cutoff = DateTime.add(DateTime.utc_now(), -7, :day)
    delete_all(from(occurrence in Occurrence, where: occurrence.inserted_at < ^cutoff))
    # An error's remaining occurrences go with it.
    delete_all(from(error in Error, where: error.last_occurrence_at < ^cutoff))
    :ok
  end

  # In batches, so one run never holds a long lock on a large table.
  defp delete_all(query) do
    batch = from(row in query, select: row.id, limit: @batch)

    case Repo.delete_all(from(row in query, where: row.id in subquery(batch))) do
      {@batch, _rows} -> delete_all(query)
      {_fewer, _rows} -> :ok
    end
  end
end
