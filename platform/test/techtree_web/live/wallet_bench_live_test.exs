defmodule TechtreeWeb.WalletBenchLiveTest do
  @moduledoc """
  What the Wallet Bench page says before any test has run.
  """

  use TechtreeWeb.ConnCase, async: false

  import Phoenix.LiveViewTest

  test "with no tests yet, it says what will appear and points to how a test runs", %{conn: conn} do
    {:ok, live, _html} = live(conn, ~p"/wallet-bench")

    assert has_element?(live, "#wallet-bench-empty")

    assert has_element?(
             live,
             ~s|#wallet-bench-empty a[href="#how-tests-run"]|,
             "See how a test runs"
           )

    assert has_element?(live, "details#how-tests-run")
    refute has_element?(live, ".wallet-bench__frame")
  end
end
