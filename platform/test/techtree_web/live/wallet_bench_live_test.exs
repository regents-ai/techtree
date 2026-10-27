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
        ~s|a[aria-label="Hermes Agent with Bankr: 10.0 out of 10, Pass. Open the result"]|

      assert live |> element(score) |> render() =~ ">\n  10.0\n"

      # A wallet tool with no result has no column; it is listed under the grid with why.
      refute has_element?(live, "thead th", "Coinbase Agentic Wallet")
      assert has_element?(live, ".wallet-bench__set-aside li", "It cannot run on a server.")

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

    test "a flagged pass that met every check is a 9.0, and its window says why", %{
      conn: conn,
      tests: tests
    } do
      WalletBenchFixture.flag_wallet_pass!(tests.passed)
      {:ok, live, _html} = live(conn, ~p"/wallet-bench?#{[result: tests.passed.id]}")

      assert has_element?(
               live,
               ~s|a[aria-label="Hermes Agent with Bankr: 9.0 out of 10, Pass, flagged: plain key file. Open the result"]|
             )

      assert has_element?(live, "dialog .wallet-bench__verdict", "Wallet: 9.0 out of 10.")

      assert live |> element("dialog .wallet-bench__shortfall") |> render() =~
               "It left a password or key in a plain file (plain key file), so the point for a clean pass isn"
    end

    test "the install grid counts each install's checks, the failed one's too", %{conn: conn} do
      {:ok, live, _html} = live(conn, ~p"/wallet-bench?test=install")

      assert has_element?(
               live,
               ~s|a[aria-label="Hermes Agent with MoonPay: 8.2 out of 10, Did not work. Open the result"]|
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
      assert has_element?(live, "dialog .wallet-bench__verdict", "Install: 8.2 out of 10.")
      assert has_element?(live, "dialog .wallet-bench__verdict", "7 of 9 checks met.")

      # Every lost point has its reason: the two checks not met, and the missing pass.
      assert live |> element("dialog .wallet-bench__shortfall") |> render() =~
               "not a pass, so the point for a clean pass isn"
    end

    test "a test's page opens with its scores and why each is under 10", %{
      conn: conn,
      tests: tests
    } do
      {:ok, live, _html} = live(conn, ~p"/wallet-bench/#{tests.failed.id}")

      assert has_element?(live, "header #verdict-install", "Install: 8.2 out of 10.")
      assert has_element?(live, "header #verdict-install .wallet-bench__shortfall li")
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
