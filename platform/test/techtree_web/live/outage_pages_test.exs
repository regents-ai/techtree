defmodule TechtreeWeb.OutagePagesTest do
  @moduledoc """
  What the public pages say when the database stops answering: that their data
  can't be shown right now, never that there is nothing there.

  Each test takes the database away after setup by returning the pool to manual
  mode, so the page's reads and the outage question both find no connection.
  """

  use TechtreeWeb.ConnCase, async: false

  import ExUnit.CaptureLog
  import Phoenix.LiveViewTest

  setup do
    Ecto.Adapters.SQL.Sandbox.mode(Techtree.Repo, :manual)
    :ok
  end

  defp quietly(fun) do
    capture_log(fn -> send(self(), {:result, fun.()}) end)
    assert_received {:result, result}
    result
  end

  test "Home says its Climbs and install command can't be shown", %{conn: conn} do
    {:ok, live, _html} = quietly(fn -> live(conn, ~p"/") end)

    assert has_element?(live, "#climbs-unreadable", "The Climbs can't be shown right now.")
    assert has_element?(live, ".release-state", "The command can't be shown right now.")
    refute render(live) =~ "There's no version of Techtree to install yet."
  end

  test "Start and Docs say the install steps can't be shown, not that there's nothing to install",
       %{conn: conn} do
    {:ok, start, _html} = quietly(fn -> live(conn, ~p"/start") end)

    assert has_element?(
             start,
             ".setup-unavailable",
             "The install steps can't be shown right now."
           )

    refute render(start) =~ "There's no version of Techtree to install yet."

    {:ok, docs, _html} = quietly(fn -> live(conn, ~p"/docs") end)
    assert has_element?(docs, "#install", "The install steps can't be shown right now.")
    refute render(docs) =~ "There's no version of Techtree to install yet."
  end

  test "Results says it can't show Results and hides the filters", %{conn: conn} do
    {:ok, live, _html} = quietly(fn -> live(conn, ~p"/results") end)

    assert has_element?(live, "#results-database-down", "Results can't be shown right now.")
    refute has_element?(live, ".results-filters")
    refute render(live) =~ "Nobody has published a Result yet."
  end

  test "Wallet Bench says its tests can't be shown, not that none have run", %{conn: conn} do
    {:ok, live, _html} = quietly(fn -> live(conn, ~p"/wallet-bench") end)

    assert has_element?(
             live,
             "#wallet-bench-unreadable",
             "Wallet tests can't be shown right now."
           )

    refute has_element?(live, "#wallet-bench-empty")
  end
end
