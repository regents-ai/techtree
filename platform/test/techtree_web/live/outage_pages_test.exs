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

  alias Techtree.Accounts.SessionAuthority
  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture

  import ExUnit.CaptureLog
  import Phoenix.ConnTest
  import Phoenix.LiveViewTest

  @endpoint TechtreeWeb.Endpoint

  alias TechtreeWeb.HealthMemory

  setup do
    # Whatever an earlier test's health check left was answered long ago.
    HealthMemory.remember(HealthMemory.now() - :timer.hours(1))
    cut_database()
    on_exit(&bring_back/0)
    {:ok, conn: build_conn()}
  end

  defp cut_database do
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

    Process.unlink(refusing)
  end

  # The usual pool, back as the suite expects it: the stand-in pool registered in
  # its place is stopped and the supervised one restarted. A test may bring it
  # back itself first; then this finds it already running.
  defp bring_back do
    case List.keyfind(Supervisor.which_children(Techtree.Supervisor), Techtree.Repo, 0) do
      {_id, :undefined, _type, _modules} ->
        if refusing = Process.whereis(Techtree.Repo), do: Supervisor.stop(refusing)
        {:ok, _pool} = Supervisor.restart_child(Techtree.Supervisor, Techtree.Repo)

      _running ->
        :ok
    end

    Ecto.Adapters.SQL.Sandbox.mode(Techtree.Repo, :manual)
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

    assert has_element?(live, "[role=status]", "Climbs can't be shown")
    assert has_element?(live, ".installer [role=status]", "can't be shown")
    refute has_element?(live, ".installer p", "no version of Techtree")
  end

  test "Start and Docs say the install steps can't be shown, not that there's nothing to install",
       %{conn: conn} do
    {:ok, start, _html} = quietly(fn -> live(conn, ~p"/start") end)

    assert has_element?(
             start,
             ".setup-unavailable [role=status] h2",
             "install steps can't be shown"
           )

    refute has_element?(start, ".setup-unavailable h2", "no version of Techtree")

    {:ok, docs, _html} = quietly(fn -> live(conn, ~p"/docs/install") end)
    assert has_element?(docs, ".doc-section [role=status]", "install steps can't be shown")
    refute has_element?(docs, ".doc-section p", "no version of Techtree")
  end

  test "Results says it can't show Results and hides the filters", %{conn: conn} do
    {:ok, live, _html} = quietly(fn -> live(conn, ~p"/results") end)

    assert has_element?(live, "[role=status]", "Results can't be shown")
    refute has_element?(live, ".results-filters")
    refute has_element?(live, ".runs-index__empty", "Nobody has published")
  end

  test "Wallet Bench says its tests can't be shown, not that none have run", %{conn: conn} do
    {:ok, live, _html} = quietly(fn -> live(conn, ~p"/wallet-bench") end)

    assert has_element?(live, "[role=status]", "Wallet tests can't be shown")

    refute has_element?(live, "[role=status]", "No wallet tests have run yet")
  end

  # A browser that holds a sign-in, made without the database: the claim's own
  # shape is all a page reads before it asks the database about it.
  defp signed_in(conn) do
    lineage = 32 |> :crypto.strong_rand_bytes() |> Base.url_encode64(padding: false)
    session = SessionAuthority.session(%{lineage: lineage, generation: 1})
    {Plug.Test.init_test_session(conn, session), session}
  end

  test "a signed-in visitor sees a public page signed out, and keeps the sign-in", %{conn: conn} do
    {conn, session} = signed_in(conn)

    conn = quietly(fn -> get(conn, ~p"/wallet-bench") end)

    assert conn
           |> html_response(200)
           |> LazyHTML.from_document()
           |> LazyHTML.query("[role=status]")
           |> LazyHTML.text() =~ "Wallet tests can't be shown"

    assert html_response(conn, 200) =~ ~s|data-account-target="sign-in"|
    refute html_response(conn, 200) =~ ~s|name="session-refused"|

    # The session the response writes back still carries the same sign-in, so
    # nothing renews, rotates or drops it.
    for {key, value} <- session, do: assert(Plug.Conn.get_session(conn, key) == value)
  end

  # The side panel is drawn by the page's outer layout, which the test client
  # doesn't connect, so its live mount is run here as a connecting socket would.
  defp connecting(session) do
    %Phoenix.LiveView.Socket{transport_pid: self(), private: %{connect_info: %{session: session}}}
  end

  @rendered %{"client_key" => "outage-test", "render_route" => "/results"}

  test "the side panel's live connection goes on signed out for a signed-in visitor" do
    {_conn, session} = signed_in(build_conn())

    assert {:cont, socket} =
             quietly(fn ->
               TechtreeWeb.Live.Session.on_mount(
                 :load_visitor,
                 %{},
                 @rendered,
                 connecting(session)
               )
             end)

    assert socket.assigns.account_control.kind == :sign_in
    assert socket.assigns.session_lease == nil
  end

  test "the account pages' live connection still fails whole" do
    {_conn, session} = signed_in(build_conn())

    assert_raise Ash.Error.Unknown, fn ->
      quietly(fn ->
        TechtreeWeb.Live.Session.on_mount(:load_human, %{}, @rendered, connecting(session))
      end)
    end
  end

  test "once the database is back, a page drawn signed out in the outage redirects once" do
    {_conn, session} = signed_in(build_conn())

    bring_back()
    Ecto.Adapters.SQL.Sandbox.checkout(Techtree.Repo)

    # The panel can now read the claim: a sign-in this browser no longer holds,
    # so it goes once to the public root, as it would with the database up
    # all along, rather than drawing signed out again or looping.
    assert {:halt, socket} =
             TechtreeWeb.Live.Session.on_mount(:load_visitor, %{}, @rendered, connecting(session))

    assert {:redirect, %{to: "/"}} = socket.redirected
  end

  # What Postgres answers first when a restart or failover ends a connection,
  # raw and as Ash passes it on.
  test "a connection Postgres shut down counts as lost" do
    shutdown = %Postgrex.Error{
      postgres: %{
        code: :admin_shutdown,
        pg_code: "57P01",
        severity: "FATAL",
        message: "terminating connection due to administrator command"
      }
    }

    assert :database_down = quietly(fn -> TechtreeWeb.Outage.read(fn -> raise shutdown end) end)

    wrapped =
      Ash.Error.Unknown.exception(
        errors: [
          Ash.Error.Unknown.UnknownError.exception(
            error:
              "** (Postgrex.Error) FATAL 57P01 (admin_shutdown) terminating connection due to administrator command"
          )
        ]
      )

    assert :database_down = quietly(fn -> TechtreeWeb.Outage.read(fn -> raise wrapped end) end)
  end

  test "any other Postgres error is raised even in an outage" do
    assert_raise Postgrex.Error, fn ->
      TechtreeWeb.Outage.read(fn ->
        raise %Postgrex.Error{
          postgres: %{
            code: :undefined_column,
            pg_code: "42703",
            severity: "ERROR",
            message: "column does not exist"
          }
        }
      end)
    end
  end

  test "a failure that isn't a lost connection is raised even in an outage" do
    assert_raise ArgumentError, "not an outage", fn ->
      TechtreeWeb.Outage.read(fn -> raise ArgumentError, "not an outage" end)
    end
  end

  test "the account pages still fail whole, since nothing on them can be shown", %{conn: conn} do
    {conn, _session} = signed_in(conn)

    assert_raise Ash.Error.Unknown, fn -> quietly(fn -> get(conn, ~p"/account") end) end
  end

  # Regression (Sentinel, v167 after-read): a health check that landed in a
  # database blip answered 503.
  test "a brief database blip after a healthy answer doesn't fail the health check", %{conn: conn} do
    bring_back()
    Ecto.Adapters.SQL.Sandbox.checkout(Techtree.Repo)
    Ecto.Adapters.SQL.Sandbox.mode(Techtree.Repo, {:shared, self()})
    CatalogFixture.use_bundle(CatalogFixture.root())
    Importer.import!(CatalogFixture.root())

    assert conn |> get(~p"/healthz") |> response(200) == "ok"

    cut_database()

    assert quietly(fn -> build_conn() |> get(~p"/healthz") |> response(200) end) == "ok"

    # The ok was given 44 seconds ago: still inside the grace.
    given_at = HealthMemory.now() - :timer.seconds(44)
    HealthMemory.remember(given_at)

    assert quietly(fn -> build_conn() |> get(~p"/healthz") |> response(200) end) == "ok"

    # An answer from the grace is not a live success: the grace still counts
    # from the last one, so a real outage can't keep the machine healthy.
    assert HealthMemory.get!(:healthy_at) == given_at

    # 46 seconds ago: the grace is over, and the loss fails the check.
    HealthMemory.remember(HealthMemory.now() - :timer.seconds(46))

    assert quietly(fn -> build_conn() |> get(~p"/healthz") |> response(503) end) == "unavailable"
  end

  test "a machine that starts during a database loss fails the check", %{conn: conn} do
    HealthMemory.delete_all()

    assert quietly(fn -> conn |> get(~p"/healthz") |> response(503) end) == "unavailable"
  end

  test "the Wallet Bench scores feed asks to try again, in JSON", %{conn: conn} do
    TechtreeWeb.WalletBenchScores.delete_all()

    conn = quietly(fn -> get(conn, ~p"/wallet-bench.json") end)

    assert Plug.Conn.get_resp_header(conn, "retry-after") == ["30"]

    assert %{"error" => %{"code" => "scores_unavailable", "message" => message}} =
             json_response(conn, 503)

    assert message =~ "try again"
  end
end
