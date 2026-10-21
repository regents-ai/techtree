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
  report each run's outcome and time from Oban's own events.
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

  import Telemetry.Metrics

  alias TechtreeWeb.Telemetry.Buckets

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
