defmodule TechtreeWeb.TelemetryTest do
  use ExUnit.Case, async: false

  import Plug.Test, only: [conn: 2]

  alias Ecto.Adapters.SQL.Sandbox
  alias Techtree.Repo

  # Every site's dashboard reads request and query time by these names, so a
  # request and a query must each land in the scrape.
  test "a request is timed by its route pattern and a query by its whole time" do
    :ok = Sandbox.checkout(Repo)

    :get |> conn("/sitemap.xml") |> TechtreeWeb.Endpoint.call(TechtreeWeb.Endpoint.init([]))
    Repo.query!("SELECT 1")

    scrape = TechtreeWeb.Telemetry.scrape()

    assert scrape =~
             ~r/^techtree_request_duration_microseconds_count\{route="\/sitemap.xml"\} [1-9]/m

    assert scrape =~ ~r/^techtree_repo_query_microseconds_count [1-9]/m
  end

  # Sentinel's job tile reads the oldest unfinished job's age in each running
  # queue. The test configuration runs no queue, so the site's job runner is
  # swapped for one that runs `probe` and `idle` and holds `held` paused, on the
  # same tables; nothing it could pick up is waiting, so it runs no job.
  describe "the oldest unfinished job in each running queue" do
    setup do
      :ok = Sandbox.checkout(Repo)
      Sandbox.mode(Repo, {:shared, self()})

      %{repo: repo, prefix: prefix} = Oban.config()
      :ok = Supervisor.terminate_child(Techtree.Supervisor, Oban)
      on_exit(fn -> {:ok, _pid} = Supervisor.restart_child(Techtree.Supervisor, Oban) end)

      start_supervised!(
        {Oban,
         repo: repo,
         prefix: prefix,
         queues: [probe: 1, idle: 1, held: [limit: 1, paused: true]],
         plugins: false,
         stager: false,
         peer: false,
         notifier: Oban.Notifiers.PG}
      )

      ref = make_ref()
      test = self()

      :telemetry.attach(
        ref,
        [:techtree, :jobs, :oldest_unfinished],
        fn _event, %{age_ms: age_ms}, %{queue: queue}, _ ->
          send(test, {:oldest, queue, age_ms})
        end,
        nil
      )

      on_exit(fn -> :telemetry.detach(ref) end)
      %{prefix: prefix}
    end

    test "is measured for running queues, 0 when empty, and never for a paused one",
         %{prefix: prefix} do
      now = DateTime.utc_now()
      job(prefix, "probe", "executing", DateTime.add(now, -90, :second), now)
      # A retry waiting for its time counts; a job only scheduled for later does not.
      job(prefix, "probe", "retryable", DateTime.add(now, -30, :second), DateTime.add(now, 3600))
      job(prefix, "idle", "scheduled", DateTime.add(now, -600, :second), DateTime.add(now, 3600))
      job(prefix, "held", "available", DateTime.add(now, -600, :second), now)

      TechtreeWeb.Telemetry.oldest_unfinished_jobs()

      assert_received {:oldest, "probe", probe_ms}
      assert probe_ms >= 90_000 and probe_ms < 600_000
      assert_received {:oldest, "idle", 0}
      refute_received {:oldest, "held", _}

      assert TechtreeWeb.Telemetry.scrape() =~
               ~r/^health_job_oldest_age_seconds\{queue="probe"\} (9\d|1\d\d)(\.\d+)?$/m
    end
  end

  defp job(prefix, queue, state, inserted_at, scheduled_at) do
    Repo.insert!(
      %Oban.Job{
        queue: queue,
        state: state,
        worker: "TechtreeWeb.TelemetryTest.Probe",
        args: %{},
        attempt: if(state == "available", do: 0, else: 1),
        inserted_at: inserted_at,
        scheduled_at: scheduled_at,
        attempted_at: if(state == "available", do: nil, else: inserted_at)
      },
      prefix: prefix
    )
  end
end
