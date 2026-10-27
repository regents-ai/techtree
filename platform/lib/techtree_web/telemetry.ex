defmodule TechtreeWeb.Telemetry do
  @moduledoc """
  The site's measurements, as `:telemetry` events, and their Prometheus export on
  the private metrics listener (`TechtreeWeb.Metrics`). Fly Sentinel's site
  watch reads the `health.*` series from every site: Ecto's
  `[:techtree, :repo, :query]` (`queue_time` is the wait for a connection),
  `[:techtree, :chain, :failure]` for each chain request that got no answer
  (`Techtree.ChainClient`), `[:techtree, :wallet, :failure]` for each press the
  browser reported as not sent or not confirmed (`wallet_failed/2`), and
  agents' activity reads that gave no reading (`Techtree.Agents.ActivityReading`).
  Every request the router sends to a page or controller is timed by its route
  pattern (`[:phoenix, :router_dispatch, :stop]`), never by its path, and every
  query by its whole time (`total_time` of the same Ecto event). Background jobs
  report each run's outcome and time from Oban's own events, and
  `[:techtree, :jobs, :oldest_unfinished]` carries `age_ms` of the oldest
  available, running or retrying job in each running `queue`, 0 when there is
  none, every ten seconds. A paused queue keeps its jobs waiting on purpose, so it
  is not measured.
  Each Result newly published (`Techtree.Network.Ingest`) is counted, and so is
  each time a browser opens a Result's page (`TechtreeWeb.RunsLive.Show`); a
  page opened by following a link on the site never passes through the router,
  so the request series alone would miss it.
  The publication rate-limit table reports each sweep. The engine's memory, run
  queues and process counts come from telemetry_poller's default poller, every
  10 seconds (`config/config.exs`).

  The reporter, Peep, keeps a fixed set of counters for each series and holds
  no observation between scrapes. It adds each observation to a running total
  as a whole number, so times are measured in whole microseconds, and every
  total stays exact.
  """

  import Ecto.Query, only: [from: 2]
  import Telemetry.Metrics

  alias TechtreeWeb.Telemetry.Buckets

  require Logger

  # The reasons the wallet hook reports (`Failure` in send_step.ts). Only these
  # are counted, so a label never holds whatever a browser chose to send.
  @wallet_failures ~w(step_unknown wallet_unavailable network_mismatch wallet_declined insufficient_funds send_unconfirmed)

  @reporter :techtree_prometheus

  def child_spec(_arg) do
    Peep.child_spec(metrics: metrics(), name: @reporter)
  end

  @doc "Every measurement as Prometheus text, as the metrics listener answers it."
  def scrape,
    do: @reporter |> Peep.get_all_metrics() |> Peep.Prometheus.export() |> IO.iodata_to_binary()

  @doc """
  Counts one press the browser reported as not sent or not confirmed, for the
  wallet-button component `flow`. A reason the hook never sends is not counted.
  """
  def wallet_failed(flow, reason) when reason in @wallet_failures do
    :telemetry.execute([:techtree, :wallet, :failure], %{count: 1}, %{
      flow: flow,
      reason: reason
    })
  end

  def wallet_failed(_flow, _reason), do: :ok

  @doc "The poller for the measurements the site takes itself, started after Oban."
  def site_poller,
    do:
      {:telemetry_poller,
       measurements: [{__MODULE__, :oldest_unfinished_jobs, []}],
       period: 10_000,
       name: :techtree_site_poller}

  # The poller drops for good a measurement that raises or exits, and the row
  # would then keep its last number. So whatever stops this tick (a database
  # that cannot answer, a queue too busy to say whether it runs, Oban or the
  # repo restarting) is logged and skipped; the next tick measures again.
  @doc false
  def oldest_unfinished_jobs do
    measure_oldest_unfinished_jobs()
  rescue
    error -> not_measured(Exception.message(error))
  catch
    :exit, reason -> not_measured(Exception.format_exit(reason))
  end

  defp not_measured(why), do: Logger.warning("background job age not measured: #{why}")

  # Only running queues are measured: a paused queue holds its jobs on purpose,
  # and its age would only grow. Where no queue runs (tests), nothing is read.
  defp measure_oldest_unfinished_jobs do
    case for %{queue: queue, paused: false} <- Oban.check_all_queues(), do: queue do
      [] -> :ok
      running -> report_oldest(running)
    end
  end

  defp report_oldest(running) do
    %{prefix: prefix} = Oban.config()

    oldest =
      from(j in Oban.Job,
        where: j.state in ["available", "executing", "retryable"],
        group_by: j.queue,
        select: {j.queue, min(j.inserted_at)}
      )
      # Oban's job table has no Ash resource; this only reads it.
      |> Techtree.Repo.all(prefix: prefix)
      |> Map.new()

    now = DateTime.utc_now()

    for queue <- running do
      age_ms =
        case oldest[queue] do
          nil -> 0
          inserted_at -> DateTime.diff(now, inserted_at, :millisecond)
        end

      :telemetry.execute([:techtree, :jobs, :oldest_unfinished], %{age_ms: age_ms}, %{
        queue: queue
      })
    end
  end

  defp metrics do
    [
      counter("techtree.privy.browser_failure.total", tags: [:reason]),
      counter("techtree.privy.session_refused.total", tags: [:stage, :reason]),
      counter("techtree.session_bootstrap.rate_limited.total", tags: [:source]),
      counter("techtree.session_authority.absent_row.total"),
      distribution("health.db_queue.microseconds",
        event_name: [:techtree, :repo, :query],
        measurement: :queue_time,
        unit: {:native, :microsecond},
        description: "Microseconds a query waited for a database connection",
        reporter_options: [
          peep_bucket_calculator: Buckets,
          buckets:
            [1_000, 5_000, 10_000, 25_000, 50_000, 100_000, 250_000, 500_000] ++
              [1_000_000, 2_500_000, 5_000_000]
        ]
      ),
      distribution("techtree.repo.query.microseconds",
        event_name: [:techtree, :repo, :query],
        measurement: :total_time,
        unit: {:native, :microsecond},
        description: "Microseconds each query took, waiting for a connection included",
        reporter_options: [
          peep_bucket_calculator: Buckets,
          buckets:
            [1_000, 5_000, 10_000, 25_000, 50_000, 100_000, 250_000, 500_000] ++
              [1_000_000, 2_500_000, 5_000_000]
        ]
      ),
      distribution("techtree.request.duration.microseconds",
        event_name: [:phoenix, :router_dispatch, :stop],
        measurement: :duration,
        unit: {:native, :microsecond},
        tags: [:route],
        description: "Microseconds each request took, by its route pattern",
        reporter_options: [
          peep_bucket_calculator: Buckets,
          buckets:
            [5_000, 10_000, 25_000, 50_000, 100_000, 250_000, 500_000, 1_000_000] ++
              [2_500_000, 5_000_000, 10_000_000]
        ]
      ),
      counter("health.chain_request_failures.total",
        event_name: [:techtree, :chain, :failure],
        tags: [:method, :class, :chain_id, :scope],
        description: "Chain requests that got no answer"
      ),
      last_value("health.job.oldest_age.seconds",
        event_name: [:techtree, :jobs, :oldest_unfinished],
        measurement: :age_ms,
        unit: {:millisecond, :second},
        tags: [:queue],
        description:
          "Age of the oldest unfinished background job in the queue, counted from when it was added"
      ),
      counter("techtree.jobs.finished.total",
        event_name: [:oban, :job, :stop],
        tags: [:queue, :worker, :state],
        description: "Job runs that ended done, cancelled or snoozed"
      ),
      counter("techtree.jobs.failed.total",
        event_name: [:oban, :job, :exception],
        tags: [:queue, :worker, :state],
        description: "Job runs that failed; state says whether the job will retry"
      ),
      distribution("techtree.jobs.duration.microseconds",
        event_name: [:oban, :job, :stop],
        measurement: :duration,
        unit: {:native, :microsecond},
        tags: [:queue, :worker],
        reporter_options: [
          peep_bucket_calculator: Buckets,
          buckets: [
            10_000,
            50_000,
            100_000,
            500_000,
            1_000_000,
            5_000_000,
            15_000_000,
            60_000_000
          ]
        ]
      ),
      counter("techtree.results.published.total",
        event_name: [:techtree, :results, :published],
        description: "Results newly published"
      ),
      counter("techtree.results.read.total",
        event_name: [:techtree, :results, :read],
        description: "Result pages opened in a browser"
      ),
      last_value("techtree.rate_limit.sweep.duration.microseconds",
        event_name: [:techtree, :rate_limit, :sweep],
        measurement: :duration
      ),
      last_value("techtree.rate_limit.sweep.deleted"),
      last_value("techtree.rate_limit.sweep.size"),
      counter("health.agent_activity_unread.total",
        event_name: [:techtree, :agents, :activity_unread],
        tags: [:reason],
        description: "Agents' activity reads from the sign-in service that gave no reading"
      ),
      last_value("vm.memory.total.bytes", event_name: [:vm, :memory], measurement: :total),
      last_value("vm.memory.processes.bytes",
        event_name: [:vm, :memory],
        measurement: :processes
      ),
      last_value("vm.memory.binary.bytes", event_name: [:vm, :memory], measurement: :binary),
      last_value("vm.memory.ets.bytes", event_name: [:vm, :memory], measurement: :ets),
      last_value("vm.memory.code.bytes", event_name: [:vm, :memory], measurement: :code),
      last_value("vm.memory.atom.bytes", event_name: [:vm, :memory], measurement: :atom),
      last_value("vm.total_run_queue_lengths.total"),
      last_value("vm.total_run_queue_lengths.cpu"),
      last_value("vm.system_counts.process_count"),
      last_value("vm.system_counts.atom_count"),
      last_value("vm.system_counts.port_count"),
      counter("health.wallet_send_failures.total",
        event_name: [:techtree, :wallet, :failure],
        tags: [:flow, :reason],
        description: "Wallet presses the browser reported as not sent or not confirmed"
      )
    ]
  end
end
