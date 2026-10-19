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

  # Postgres ending the connection (class 57P), and the connection itself
  # failing (class 08).
  @lost [
    {:admin_shutdown, "57P01"},
    {:crash_shutdown, "57P02"},
    {:cannot_connect_now, "57P03"},
    {:connection_exception, "08000"},
    {:connection_does_not_exist, "08003"},
    {:connection_failure, "08006"},
    {:sqlclient_unable_to_establish_sqlconnection, "08001"},
    {:sqlserver_rejected_establishment_of_sqlconnection, "08004"},
    {:transaction_resolution_unknown, "08007"},
    {:protocol_violation, "08P01"}
  ]
  @lost_states Enum.map(@lost, &elem(&1, 1))
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
      map(member_of(@lost), fn {code, state} -> postgres(code, state) end),
      map(string(:printable), &ash_text("** (DBConnection.ConnectionError) " <> &1)),
      map(
        tuple({member_of(~w(FATAL ERROR)), member_of(@lost_states), string(:printable)}),
        fn {severity, state, rest} ->
          ash_text("** (Postgrex.Error) #{severity} #{state} " <> rest)
        end
      )
    ])
  end

  defp other_failure do
    one_of([
      map(member_of(@other_codes), fn {code, state} -> postgres(code, state) end),
      map(tuple({member_of(@other_codes), string(:printable)}), fn {{_code, state}, rest} ->
        ash_text("** (Postgrex.Error) ERROR #{state} " <> rest)
      end),
      # Fatal, but not about the connection: a bad password or a missing database.
      map(tuple({member_of(~w(28P01 3D000 53300)), string(:printable)}), fn {state, rest} ->
        ash_text("** (Postgrex.Error) FATAL #{state} " <> rest)
      end),
      # A shutdown code later in an ordinary error's message is still an ordinary error.
      map(tuple({member_of(@other_codes), member_of(@lost_states)}), fn {{_code, state}, lost} ->
        ash_text("** (Postgrex.Error) ERROR #{state} relation mentions #{lost}")
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
