defmodule TechtreeWeb.Telemetry do
  @moduledoc """
  The site's measurements, as `:telemetry` events, and their Prometheus export on
  the private metrics listener (`TechtreeWeb.Metrics`). Fly Sentinel's site
  watch reads the `health.*` series from every site: Ecto's
  `[:techtree, :repo, :query]` (`queue_time` is the wait for a connection),
  `[:techtree, :chain, :failure]` for each chain request that got no answer
  (`Techtree.ChainClient`),
  agents' activity reads that gave no reading (`Techtree.Agents.ActivityReading`),
  and the clock time the Points tally of finished periods last ran to its end
  (`[:regent_points, :tally_periods, :finished]`), so a stalled tally shows as a
  time that stops moving.
  Every request the router sends to a page or controller is timed by its route
  pattern (`[:phoenix, :router_dispatch, :stop]`), never by its path, and every
  query by its whole time (`total_time` of the same Ecto event). Background jobs
  report each run's outcome and time from Oban's own events, and
  `[:techtree, :jobs, :oldest_unfinished]` carries `age_ms` of the oldest
  available, running or retrying job in each running `queue`, 0 when there is
  none, every ten seconds. A paused queue keeps its jobs waiting on purpose, so it
  is not measured.
  The site sends from its own wallet (the Wallet Bench's funder), so it names, as
  `unconfirmed_sends` in `config :techtree, TechtreeWeb.Telemetry`, the function
  that answers each of its fixed sending flows with when its oldest signed,
  unconfirmed transaction was signed, or nil; every ten seconds
  `[:techtree, :wallet, :unconfirmed_oldest]` carries that `age_ms` for each
  `flow`, 0 when none waits.
  Each Result newly published (`Techtree.Network.Ingest`) is counted, and so is
  each time a browser opens a Result's page (`TechtreeWeb.RunsLive.Show`); a
  page opened by following a link on the site never passes through the router,
  so the request series alone would miss it.
  The figures every reader they admit sees alike (`Techtree.SharedReading`) report, for
  each kind, how many keys are held, how many have never been read, how long ago
  the oldest was read, the size of each reading offered as a percent of its kind's
  limit, each reading that could not be taken and each one refused.
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

  @reporter :techtree_prometheus

  def child_spec(_arg) do
    Peep.child_spec(metrics: metrics(), name: @reporter)
  end

  @doc "Every measurement as Prometheus text, as the metrics listener answers it."
  def scrape,
    do: @reporter |> Peep.get_all_metrics() |> Peep.Prometheus.export() |> IO.iodata_to_binary()

  @doc "The poller for the measurements the site takes itself, started after Oban."
  def site_poller,
    do:
      {:telemetry_poller,
       measurements:
         [
           {Techtree.SharedReading, :measure, []},
           {__MODULE__, :oldest_unfinished_jobs, []}
         ] ++ unconfirmed_sends_step(),
       period: 10_000,
       name: :techtree_site_poller}

  # Only a site that sends from its own wallet names its query. Without one the
  # age is never published, so Sentinel never reads a steady 0 that only means
  # nothing was asked.
  defp unconfirmed_sends_step do
    case Application.get_env(:techtree, __MODULE__)[:unconfirmed_sends] do
      nil -> []
      query -> [{__MODULE__, :oldest_unconfirmed_sends, [query]}]
    end
  end

  # The poller drops for good a measurement that raises or exits, and the row
  # would then keep its last number. So whatever stops this tick (a database
  # that cannot answer, a queue too busy to say whether it runs, Oban or the
  # repo restarting) is logged and skipped; the next tick measures again.
  @doc false
  def oldest_unfinished_jobs do
    measure_oldest_unfinished_jobs()
  rescue
    error -> not_measured("background job age", Exception.message(error))
  catch
    :exit, reason -> not_measured("background job age", Exception.format_exit(reason))
  end

  # The site's query, `{module, function, args}`, answers `{flow, signed_at}`
  # for each of its sending flows, `signed_at` nil when nothing waits. Logged
  # and skipped like the job age.
  @doc false
  def oldest_unconfirmed_sends({module, function, args}) do
    now = DateTime.utc_now()

    for {flow, signed_at} <- apply(module, function, args) do
      age_ms =
        case signed_at do
          nil -> 0
          signed_at -> DateTime.diff(now, signed_at, :millisecond)
        end

      :telemetry.execute([:techtree, :wallet, :unconfirmed_oldest], %{age_ms: age_ms}, %{
        flow: flow
      })
    end

    :ok
  rescue
    error -> not_measured("unconfirmed send age", Exception.message(error))
  catch
    :exit, reason -> not_measured("unconfirmed send age", Exception.format_exit(reason))
  end

  defp not_measured(what, why), do: Logger.warning("#{what} not measured: #{why}")

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
      last_value("health.points_tally_finished.seconds",
        event_name: [:regent_points, :tally_periods, :finished],
        measurement: fn _measurements -> System.system_time(:second) end,
        description:
          "When the Points tally of finished periods last ran to its end, in Unix seconds"
      ),
      last_value("health.job.oldest_age.seconds",
        event_name: [:techtree, :jobs, :oldest_unfinished],
        measurement: :age_ms,
        unit: {:millisecond, :second},
        tags: [:queue],
        description:
          "Age of the oldest unfinished background job in the queue, counted from when it was added"
      ),
      last_value("health.wallet_unconfirmed_oldest.seconds",
        event_name: [:techtree, :wallet, :unconfirmed_oldest],
        measurement: :age_ms,
        unit: {:millisecond, :second},
        tags: [:flow],
        description:
          "Age of the oldest transaction the site's own wallet signed that is not yet confirmed"
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
      last_value("health.shared_reading.oldest.seconds",
        event_name: [:techtree, :shared_reading, :kind],
        measurement: :oldest_seconds,
        tags: [:kind],
        description: "Seconds since the oldest shared reading of each kind was read"
      ),
      last_value("health.shared_reading.late.keys",
        event_name: [:techtree, :shared_reading, :kind],
        measurement: :late,
        tags: [:kind],
        description: "Keys of the kind last read longer ago than the kind's producer should allow"
      ),
      last_value("health.shared_reading.size.percent",
        event_name: [:techtree, :shared_reading, :size],
        measurement: &div(&1.bytes * 100, &1.limit),
        tags: [:kind],
        description:
          "Size of the last reading each kind was offered, as a percent of the kind's limit; " <>
            "past 100 it is refused and the last one held stays"
      ),
      last_value("health.shared_reading.never_read.keys",
        event_name: [:techtree, :shared_reading, :kind],
        measurement: :never_read,
        tags: [:kind],
        description: "Keys of the kind that have had no reading since the site started"
      ),
      counter("health.shared_reading.degraded.total",
        event_name: [:techtree, :shared_reading, :degraded],
        tags: [:kind],
        description: "Shared readings that could not be taken"
      ),
      last_value("techtree.shared_reading.keys",
        event_name: [:techtree, :shared_reading, :kind],
        measurement: :keys,
        tags: [:kind]
      ),
      last_value("techtree.shared_reading.table.bytes",
        event_name: [:techtree, :shared_reading, :table],
        measurement: :bytes
      ),
      counter("techtree.shared_reading.refused.total",
        event_name: [:techtree, :shared_reading, :refused],
        tags: [:kind, :reason]
      ),
      counter("techtree.shared_reading.woken.total",
        event_name: [:techtree, :shared_reading, :woken],
        tags: [:kind]
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
      last_value("vm.system_counts.port_count")
    ]
  end
end
