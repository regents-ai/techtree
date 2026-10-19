defmodule TechtreeWeb.WalletBenchLiveTest do
  @moduledoc """
  The Wallet Bench page: what it says before any test has run, the score grid
  for each test, a result opened in its window and closed again, and the list.
  """

  use TechtreeWeb.ConnCase, async: false

  import Phoenix.LiveViewTest

  alias Techtree.WalletBenchFixture

  test "with no tests yet, it says what will appear and points to how a test runs", %{conn: conn} do
    {:ok, live, _html} = live(conn, ~p"/wallet-bench")

    assert has_element?(live, "[role=status]", "No wallet tests have run yet")
    assert has_element?(live, ~s|[role=status] a[href="#how-tests-run"]|, "See how a test runs")

    assert has_element?(live, "details#how-tests-run")
    refute has_element?(live, "table")
  end

  describe "with recorded tests" do
    setup do
      %{tests: WalletBenchFixture.seed!()}
    end

    test "each box is a score that opens its result, and closing it goes back to the grid", %{
      conn: conn,
      tests: tests
    } do
      {:ok, live, _html} = live(conn, ~p"/wallet-bench")

      score =
        ~s|a[aria-label="Hermes Agent with Bankr: 9 of 9 checks met, Pass. Open the result"]|

      assert live |> element(score) |> render() =~ ">\n  9\n"

      # A wallet tool that can't run on the bench is marked in every row.
      assert has_element?(live, "td span[title='It cannot run on a server.']", "N/A")

      live |> element(score) |> render_click()
      assert_patch(live, ~p"/wallet-bench?#{[result: tests.passed.id]}")
      assert has_element?(live, "dialog[aria-labelledby=result-title] h2", "Hermes Agent × Bankr")
      assert has_element?(live, "dialog h3", "Wallet")
      refute has_element?(live, "dialog h3", "Install")

      assert has_element?(
               live,
               ~s|dialog a[href="/wallet-bench/#{tests.passed.id}/results.zip"]|,
               "Download full results"
             )

      live |> element("dialog") |> render_hook("close_result", %{})
      assert_patch(live, ~p"/wallet-bench")
      refute has_element?(live, "dialog")
    end

    test "the install grid counts each install's checks, the failed one's too", %{conn: conn} do
      {:ok, live, _html} = live(conn, ~p"/wallet-bench?test=install")

      assert has_element?(
               live,
               ~s|a[aria-label="Hermes Agent with MoonPay: 7 of 9 checks met, Did not work. Open the result"]|
             )

      # Cline takes the install tests only, so it has a row here and not in the wallet grid.
      assert has_element?(live, "th[scope=row]", "Cline")
      {:ok, wallet, _html} = live(conn, ~p"/wallet-bench")
      refute has_element?(wallet, "th[scope=row]", "Cline")
    end

    test "a result opened by its address shows on load", %{conn: conn, tests: tests} do
      {:ok, live, _html} =
        live(conn, ~p"/wallet-bench?#{[test: "install", result: tests.failed.id]}")

      assert has_element?(live, "dialog h2", "Hermes Agent × MoonPay")
      assert has_element?(live, "dialog", "7 of 9 checks met. Did not work.")
    end

    test "the list view shows every test, newest first", %{conn: conn, tests: tests} do
      {:ok, live, _html} = live(conn, ~p"/wallet-bench?view=list")

      for {_outcome, attempt} <- tests do
        assert has_element?(
                 live,
                 ~s|#attempt-#{attempt.id} a[href="/wallet-bench/#{attempt.id}"]|
               )
      end
    end

    test "an address naming no test, view or result is not found", %{conn: conn} do
      for path <- [
            ~p"/wallet-bench?test=money",
            ~p"/wallet-bench?view=table",
            ~p"/wallet-bench?#{[result: Ecto.UUID.generate()]}"
          ] do
        assert_error_sent 404, fn -> get(conn, path) end
      end
    end
  end
end
