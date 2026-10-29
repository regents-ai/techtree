defmodule Techtree.Watchdog.Limits do
  @moduledoc """
  The Watchdog caps, read from `config :techtree, Techtree.Watchdog`: how many
  hosts one account may claim, and how many routes it may list across them.
  """

  @spec fetch!(atom()) :: pos_integer()
  def fetch!(key) do
    :techtree
    |> Application.fetch_env!(Techtree.Watchdog)
    |> Keyword.fetch!(key)
  end

  @doc "How many hosts one account may claim."
  @spec max_hosts() :: pos_integer()
  def max_hosts, do: fetch!(:max_hosts_per_account)

  @doc "How many routes one account may list across all its hosts."
  @spec max_routes() :: pos_integer()
  def max_routes, do: fetch!(:max_routes_per_account)
end
