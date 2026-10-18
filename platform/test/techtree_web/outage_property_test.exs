defmodule TechtreeWeb.OutagePropertyTest do
  @moduledoc """
  The one rule the outage handling keeps, over many failures: a read gives the
  outage note exactly when it lost its database connection, and every other
  failure is raised as it was.
  """

  use ExUnit.Case, async: true
  use ExUnitProperties

  import ExUnit.CaptureLog

  alias TechtreeWeb.Outage

  @lost_states ~w(57P01 57P02 57P03)
  @lost_codes [:admin_shutdown, :crash_shutdown, :cannot_connect_now]
  # Postgres errors a read can meet that say nothing about the connection.
  @other_codes [
    {:query_canceled, "57014"},
    {:unique_violation, "23505"},
    {:syntax_error, "42601"},
    {:undefined_column, "42703"},
    {:serialization_failure, "40001"},
    {:too_many_connections, "53300"}
  ]

  defp postgres(code, state),
    do: %Postgrex.Error{
      postgres: %{code: code, pg_code: state, severity: "FATAL", message: "from the generator"}
    }

  defp ash_text(text),
    do:
      Ash.Error.Unknown.exception(errors: [Ash.Error.Unknown.UnknownError.exception(error: text)])

  defp lost_connection do
    one_of([
      map(string(:printable), &DBConnection.ConnectionError.exception/1),
      map(member_of(Enum.zip(@lost_codes, @lost_states)), fn {code, state} ->
        postgres(code, state)
      end),
      map(string(:printable), &ash_text("** (DBConnection.ConnectionError) " <> &1)),
      map(tuple({member_of(@lost_states), string(:printable)}), fn {state, rest} ->
        ash_text("** (Postgrex.Error) FATAL #{state} " <> rest)
      end)
    ])
  end

  defp other_failure do
    one_of([
      map(member_of(@other_codes), fn {code, state} -> postgres(code, state) end),
      map(tuple({member_of(@other_codes), string(:printable)}), fn {{_code, state}, rest} ->
        ash_text("** (Postgrex.Error) ERROR #{state} " <> rest)
      end),
      # A bug's own message may well mention a shutdown code or the error's name.
      map(tuple({member_of(@lost_states), string(:printable)}), fn {state, rest} ->
        RuntimeError.exception("FATAL #{state} DBConnection.ConnectionError " <> rest)
      end),
      map(string(:printable), &ArgumentError.exception/1),
      map(string(:printable), &ash_text/1)
    ])
  end

  property "a lost connection gives the outage note" do
    check all(error <- lost_connection()) do
      capture_log(fn -> assert Outage.read(fn -> raise error end) == :database_down end)
    end
  end

  property "any other failure is raised as it was" do
    check all(error <- other_failure()) do
      raised = assert_raise(error.__struct__, fn -> Outage.read(fn -> raise error end) end)
      assert raised == error
    end
  end
end
