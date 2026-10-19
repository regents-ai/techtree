defmodule TechtreeWeb.HealthMemory do
  @moduledoc """
  The last healthy answer `/healthz` gave, kept on this machine for 45 seconds:
  three of Fly's 15-second checks. A check that lands in a brief database blip
  answers from it, so one failed probe doesn't take the machine out of service;
  a loss that outlasts it does.
  """
  use Nebulex.Cache, otp_app: :techtree, adapter: Nebulex.Adapters.Local

  @kept :timer.seconds(45)

  @spec remember(map()) :: map()
  def remember(summary) do
    put!(:healthy, summary, ttl: @kept)
    summary
  end

  @spec last_healthy() :: map() | nil
  def last_healthy, do: get!(:healthy)
end
