defmodule TechtreeWeb.OutagePagesTest do
  @moduledoc """
  What the public pages say when the database stops answering: that their data
  can't be shown right now, never that there is nothing there.

  Each test swaps the site's database pool for one pointed at a port nothing
  listens on, so every read and the outage question meet a refused connection,
  as they would in a real outage. The usual pool comes back afterwards.
  """

  use ExUnit.Case, async: false

  use TechtreeWeb, :verified_routes

  import ExUnit.CaptureLog
  import Phoenix.ConnTest
  import Phoenix.LiveViewTest

  @endpoint TechtreeWeb.Endpoint

  setup do
    :ok = Supervisor.terminate_child(Techtree.Supervisor, Techtree.Repo)

    {:ok, refusing} =
      Techtree.Repo.start_link(
        hostname: "127.0.0.1",
        socket_dir: nil,
        port: closed_port(),
        pool: DBConnection.ConnectionPool,
        pool_size: 1,
        queue_target: 10,
        queue_interval: 20,
        backoff_min: 10
      )

    on_exit(fn ->
      ref = Process.monitor(refusing)
      Process.exit(refusing, :shutdown)
      assert_receive {:DOWN, ^ref, :process, _pid, _reason}, 5_000
      {:ok, _pool} = Supervisor.restart_child(Techtree.Supervisor, Techtree.Repo)
      Ecto.Adapters.SQL.Sandbox.mode(Techtree.Repo, :manual)
    end)

    {:ok, conn: build_conn()}
  end

  # A port that was free a moment ago, so a connection to it is refused.
  defp closed_port do
    {:ok, socket} = :gen_tcp.listen(0, [])
    {:ok, port} = :inet.port(socket)
    :ok = :gen_tcp.close(socket)
    port
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
