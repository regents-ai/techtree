defmodule TechtreeWeb.Metrics do
  @moduledoc """
  Prometheus metrics on a listener of their own, which the public endpoint
  never routes to.

  In production it listens on the port `fly.toml` names under `[metrics]`. Fly
  sends public traffic only to the `[http_service]` port, so this one is
  reachable from the app's private network, where Fly's scraper reads it, and
  not from the internet. Locally it listens on loopback, on a port the system
  picks.
  """

  @behaviour Plug

  import Plug.Conn

  def child_spec(_arg) do
    :techtree
    |> Application.fetch_env!(:metrics_listener)
    |> Keyword.merge(plug: __MODULE__, startup_log: false)
    |> Bandit.child_spec()
  end

  @impl Plug
  def init(opts), do: opts

  @impl Plug
  def call(%Plug.Conn{method: "GET", path_info: ["metrics"]} = conn, _opts) do
    body = TelemetryMetricsPrometheus.Core.scrape(TechtreeWeb.Telemetry.prometheus_reporter())

    conn
    |> put_resp_content_type("text/plain")
    |> send_resp(:ok, body)
  end

  def call(conn, _opts), do: send_resp(conn, :not_found, "")
end
