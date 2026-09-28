defmodule Techtree.RateLimitTest do
  use ExUnit.Case, async: true

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
end
