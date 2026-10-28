defmodule TechtreeWeb.HealthMemoryTest do
  @moduledoc """
  The health check's grace, on an injected clock. Every answer these tests
  remember was given at least a minute before now, so none is recent for the
  tests after them.
  """
  use ExUnit.Case, async: false
  use ExUnitProperties

  alias TechtreeWeb.HealthMemory

  property "an ok is remembered for exactly 45 seconds" do
    now = HealthMemory.now()

    check all(ago <- integer(90_000..1_000_000_000), later <- integer(0..90_000)) do
      HealthMemory.remember(now - ago)

      assert HealthMemory.recent?(now - ago + later) == later < 45_000
    end
  end

  test "both sides of the edge" do
    at = HealthMemory.now() - :timer.minutes(1)
    HealthMemory.remember(at)

    assert HealthMemory.recent?(at + 44_999)
    refute HealthMemory.recent?(at + 45_000)
  end
end
