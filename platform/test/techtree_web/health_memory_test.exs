defmodule TechtreeWeb.HealthMemoryTest do
  @moduledoc """
  The health check's grace, on an injected clock. Every answer these tests
  remember was given at least a minute before now, so none is recent for the
  tests after them.
  """
  use ExUnit.Case, async: false
  use ExUnitProperties

  alias TechtreeWeb.HealthMemory

  property "a healthy answer is remembered for exactly 45 seconds" do
    now = HealthMemory.now()

    check all(ago <- integer(90_000..1_000_000_000), later <- integer(0..90_000)) do
      summary = %{status: :ok, ago: ago}
      HealthMemory.remember(summary, now - ago)
      expected = if later < 45_000, do: summary

      assert HealthMemory.last_healthy(now - ago + later) == expected
    end
  end

  test "both sides of the edge" do
    summary = %{status: :ok}
    at = HealthMemory.now() - :timer.minutes(1)
    HealthMemory.remember(summary, at)

    assert HealthMemory.last_healthy(at + 44_999) == summary
    assert HealthMemory.last_healthy(at + 45_000) == nil
  end
end
