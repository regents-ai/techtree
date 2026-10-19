defmodule TechtreeWeb.HealthMemory do
  @moduledoc """
  The last healthy answer `/healthz` gave, and when, on this machine's
  monotonic clock in milliseconds. For 45 seconds after it, three of Fly's
  15-second checks, a check that lands in a brief database blip answers from
  it, so one failed probe doesn't take the machine out of service; a loss that
  outlasts it does.
  """
  use Nebulex.Cache, otp_app: :techtree, adapter: Nebulex.Adapters.Local

  @grace :timer.seconds(45)

  @spec remember(map(), integer()) :: map()
  def remember(summary, at \\ now()) do
    put!(:healthy, {summary, at})
    summary
  end

  @doc "The last healthy answer if it was given less than 45 seconds before `now`."
  @spec last_healthy(integer()) :: map() | nil
  def last_healthy(now \\ now()) do
    case get!(:healthy) do
      {summary, at} when now - at < @grace -> summary
      _none_recent -> nil
    end
  end

  @doc "This machine's monotonic clock, in milliseconds."
  @spec now() :: integer()
  def now, do: System.monotonic_time(:millisecond)
end
