defmodule Techtree.Application do
  # See https://hexdocs.pm/elixir/Application.html
  # for more information on OTP Applications
  @moduledoc false

  use Application

  @impl true
  def start(_type, _args) do
    children = [
      TechtreeWeb.Telemetry,
      Techtree.Repo,
      {DNSCluster, query: Application.get_env(:techtree, :dns_cluster_query) || :ignore},
      {Phoenix.PubSub, name: Techtree.PubSub},
      # Start a worker by calling: Techtree.Worker.start_link(arg)
      # {Techtree.Worker, arg},
      # Start to serve requests, typically the last entry
      TechtreeWeb.Endpoint
    ]

    # See https://hexdocs.pm/elixir/Supervisor.html
    # for other strategies and supported options
    opts = [strategy: :one_for_one, name: Techtree.Supervisor]
    Supervisor.start_link(children, opts)
  end

  # Tell Phoenix to update the endpoint configuration
  # whenever the application is updated.
  @impl true
  def config_change(changed, _new, removed) do
    TechtreeWeb.Endpoint.config_change(changed, removed)
    :ok
  end
end
