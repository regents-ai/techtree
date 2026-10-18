defmodule TechtreeWeb.Outage do
  @moduledoc """
  A page's database reads, told apart from the database not answering at all.

  When the reads raise, the page asks the database one trivial question. If it
  answers, the failure belongs to the page and is raised again unchanged, so a
  bug still shows as one. Only when it doesn't answer does the page say it
  can't show its data right now instead of failing whole, and the failure is
  logged here, since the error tracker keeps its records in that same database.
  """

  require Logger

  alias Techtree.Repo

  # A database that hangs rather than refusing shouldn't hold the page for long.
  @question_timeout_ms 1_000

  @spec read((-> value)) :: {:ok, value} | :database_down when value: term()
  def read(reads) do
    {:ok, reads.()}
  rescue
    error ->
      if answering?() do
        reraise error, __STACKTRACE__
      else
        Logger.warning(
          "Database not answering; page shows its outage note: " <> Exception.message(error)
        )

        :database_down
      end
  end

  # Refusing a connection is not answering, whether the query reports it or the
  # pool raises because no connection can be had.
  defp answering? do
    match?({:ok, _result}, Repo.query("SELECT 1", [], timeout: @question_timeout_ms))
  rescue
    _no_connection in [DBConnection.ConnectionError, DBConnection.OwnershipError] -> false
  end
end
