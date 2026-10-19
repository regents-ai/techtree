defmodule Techtree.RateLimitTest do
  use ExUnit.Case, async: true
  use ExUnitProperties

  alias Techtree.RateLimit

  test "a sweep deletes the windows that have turned over and keeps the rest" do
    caller = make_ref()
    window = 60
    now = System.system_time(:second)

    {:ok, _budget} = RateLimit.admit(caller, 10, window, now - 2 * window)
    {:ok, _budget} = RateLimit.admit(caller, 10, window, now + window)

    send(RateLimit, :sweep)
    :sys.get_state(RateLimit)

    assert :ets.select(RateLimit, [{{{caller, window, :"$1"}, :_}, [], [:"$1"]}]) ==
             [div(now + window, window)]
  end

  property "a caller refused in one window is admitted again once it turns over" do
    check all(
            limit <- integer(1..20),
            window <- integer(1..3_600),
            offset <- integer(0..(window - 1))
          ) do
      caller = make_ref()
      start = div(System.system_time(:second), window) * window + offset

      for _request <- 1..limit,
          do: assert({:ok, _budget} = RateLimit.admit(caller, limit, window, start))

      assert {:error, :rate_limited, %{remaining: 0, reset: reset}} =
               RateLimit.admit(caller, limit, window, start)

      assert reset == window - offset

      assert {:ok, %{remaining: remaining}} =
               RateLimit.admit(caller, limit, window, start + reset)

      assert remaining == limit - 1
    end
  end
end
