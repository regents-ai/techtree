defmodule TechtreeWeb.HealthMemory do
  @moduledoc """
  When `/healthz` last answered `ok`, on this machine's monotonic clock in
  milliseconds. For 45 seconds after it, three of Fly's 15-second checks, a
  check that lands in a brief database blip still answers `ok`, so one failed
  probe doesn't take the machine out of service; a loss that outlasts it does.
  """
  use Nebulex.Cache, otp_app: :techtree, adapter: Nebulex.Adapters.Local

  @grace :timer.seconds(45)

  @doc "Notes that `/healthz` answered `ok` at `at`."
  @spec remember(integer()) :: :ok
  def remember(at \\ now()), do: put!(:healthy_at, at)

  @doc "Whether `/healthz` answered `ok` less than 45 seconds before `now`."
  @spec recent?(integer()) :: boolean()
  def recent?(now \\ now()) do
    case get!(:healthy_at) do
      at when is_integer(at) -> now - at < @grace
      nil -> false
    end
  end

  @doc "This machine's monotonic clock, in milliseconds."
  @spec now() :: integer()
  def now, do: System.monotonic_time(:millisecond)
end
