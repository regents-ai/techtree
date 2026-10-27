defmodule Techtree.Application do
  # See https://hexdocs.pm/elixir/Application.html
  # for more information on OTP Applications
  @moduledoc false

  use Application

  @impl true
  def start(_type, _args) do
    # Every outbound TLS connection trusts castore's list, not the operating
    # system's: castore drops a compromised root as soon as Mozilla does, which a
    # Debian image can lag by weeks. Req, Finch and Mint read this list through
    # `:public_key.cacerts_get/0`, so it is loaded before anything connects.
    :ok = :public_key.cacerts_load(CAStore.file_path())
    :ok = Techtree.JobFailure.attach()
    :ok = TechtreeWeb.VisitLog.Events.attach()

    children =
      [
        TechtreeWeb.Telemetry,
        Techtree.Accounts.RequestRateLimiter,
        Techtree.Repo,
        {DNSCluster, query: Application.get_env(:techtree, :dns_cluster_query) || :ignore},
        {Phoenix.PubSub, name: Techtree.PubSub},
        {Oban,
         AshOban.config(
           Application.fetch_env!(:techtree, :ash_domains),
           Application.fetch_env!(:techtree, Oban)
         )},
        TechtreeWeb.Telemetry.site_poller(),
        Techtree.SharedChanges,
        Techtree.Agents.ActivityReading,
        TechtreeWeb.HealthMemory,
        TechtreeWeb.GithubStars,
        TechtreeWeb.GithubStars.Reader,
        {Registry, keys: :duplicate, name: TechtreeWeb.ResultsDownloads},
        TechtreeWeb.WalletBenchScores,
        # Each agent's reading for an open side panel, unlinked from the page.
        {Task.Supervisor, name: Techtree.Agents.Reads},
        Techtree.RateLimit,
        # Start a worker by calling: Techtree.Worker.start_link(arg)
        # {Techtree.Worker, arg},
        # Start to serve requests, typically the last entry
        TechtreeWeb.Endpoint,
        metrics_child()
      ]
      |> Enum.reject(&is_nil/1)

    # See https://hexdocs.pm/elixir/Supervisor.html
    # for other strategies and supported options
    opts = [strategy: :one_for_one, name: Techtree.Supervisor]
    Supervisor.start_link(children, opts)
  end

  # Metrics are served beside the site, never by a process that only runs a task.
  defp metrics_child do
    if Phoenix.Endpoint.server?(:techtree, TechtreeWeb.Endpoint),
      do: TechtreeWeb.Metrics
  end

  # Tell Phoenix to update the endpoint configuration
  # whenever the application is updated.
  @impl true
  def config_change(changed, _new, removed) do
    TechtreeWeb.Endpoint.config_change(changed, removed)
    :ok
  end
end
