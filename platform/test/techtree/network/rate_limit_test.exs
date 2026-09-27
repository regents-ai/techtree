defmodule Techtree.Network.RateLimitTest do
  use ExUnit.Case, async: true

  alias Techtree.Network
  alias Techtree.Network.RateLimit

  test "a sweep deletes the windows that have turned over and keeps the rest" do
    caller = make_ref()
    window = Keyword.fetch!(Network.rate_limit(), :window_seconds)
    now = System.system_time(:second)

    :ok = RateLimit.allow(caller, now - 2 * window)
    :ok = RateLimit.allow(caller, now + window)

    send(RateLimit, :sweep)
    :sys.get_state(RateLimit)

    assert :ets.select(RateLimit, [{{{caller, :"$1"}, :_}, [], [:"$1"]}]) ==
             [div(now + window, window)]
  end
end
