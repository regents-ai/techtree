defmodule TechtreeWeb.Outage do
  @moduledoc """
  A page's database reads, told apart from the database not answering at all.

  A read that raised counts as an outage only when it lost its connection to the
  database and the database then doesn't answer one trivial question. Anything
  else, a bug, a slow query or a connection lost while the database still
  answers, is raised again unchanged, so it still shows as what it is. In an
  outage the page says it can't show its data right now instead of failing
  whole, and the failure is logged here, since the error tracker keeps its
  records in that same database.
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
      if not connection_lost?(error) or answering?() do
        reraise error, __STACKTRACE__
      else
        Logger.warning(
          "Database not answering; page shows its outage note: " <> Exception.message(error)
        )

        :database_down
      end
  end

  # Ash keeps a data-layer failure only as its formatted text, which opens with
  # the name of the exception, so that name is what says the connection was lost.
  defp connection_lost?(%DBConnection.ConnectionError{}), do: true

  defp connection_lost?(%Ash.Error.Unknown{errors: errors}),
    do: Enum.any?(errors, &connection_lost?/1)

  defp connection_lost?(%Ash.Error.Unknown.UnknownError{
         error: "** (DBConnection.ConnectionError)" <> _
       }),
       do: true

  defp connection_lost?(_error), do: false

  # Asked without queueing for a connection, so a database that refuses them
  # answers no at once rather than after the pool's wait.
  defp answering?,
    do:
      match?(
        {:ok, _result},
        Repo.query("SELECT 1", [], queue: false, timeout: @question_timeout_ms)
      )
end
