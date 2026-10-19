defmodule TechtreeWeb.Outage do
  @moduledoc """
  A page's database reads, with a lost connection told apart from every other failure.

  A read that raised counts as an outage when it lost its connection to the
  database: the pool couldn't reach it, or Postgres ended the connection. That is
  never the page's own fault, so the page says it can't show its data right now
  instead of failing whole. It covers the seconds after a restart too, when each
  pooled connection fails once before the pool replaces it. Anything else, a bug
  or a query error, is raised again unchanged, so it still shows as what it is.
  The failure is logged here, since the error tracker keeps its records in that
  same database.
  """

  require Logger

  @spec read((-> value)) :: {:ok, value} | :database_down when value: term()
  def read(reads) do
    {:ok, reads.()}
  rescue
    error ->
      if connection_lost?(error) do
        Logger.warning(
          "Database connection lost; page shows its outage note: " <> Exception.message(error)
        )

        :database_down
      else
        reraise error, __STACKTRACE__
      end
  end

  # A connection is lost when the pool can't reach the database, when the
  # connection itself fails (SQLSTATE class 08), or when Postgres ends it: a
  # restart or failover answers first with a shutdown, and a server still
  # starting with "cannot connect now" (class 57P).
  defp connection_lost?(%DBConnection.ConnectionError{}), do: true
  defp connection_lost?(%Postgrex.Error{postgres: %{pg_code: state}}), do: lost_state?(state)

  defp connection_lost?(%Ash.Error.Unknown{errors: errors}),
    do: Enum.any?(errors, &connection_lost?/1)

  # Ash keeps a data-layer failure only as its formatted text, which opens with
  # the exception's name and, for Postgres, the severity and SQLSTATE.
  defp connection_lost?(%Ash.Error.Unknown.UnknownError{
         error: "** (DBConnection.ConnectionError)" <> _
       }),
       do: true

  defp connection_lost?(%Ash.Error.Unknown.UnknownError{error: "** (Postgrex.Error) " <> text}) do
    case String.split(text, " ", parts: 3) do
      [_severity, state | _message] -> lost_state?(state)
      _other -> false
    end
  end

  defp connection_lost?(_error), do: false

  defp lost_state?("08" <> _connection_exception), do: true
  defp lost_state?(state), do: state in ["57P01", "57P02", "57P03"]
end
