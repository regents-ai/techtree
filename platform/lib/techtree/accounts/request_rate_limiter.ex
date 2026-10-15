defmodule Techtree.Accounts.RequestRateLimiter do
  @moduledoc """
  Per-client fixed-window budgets in one ETS table, each answer carrying what is
  left of the window. This is a per-instance best-effort bound, not a global
  cap: with N instances a client can spend N × limit in one window. Replace it
  with a distributed budget before horizontal scaling.
  """

  use GenServer

  @table __MODULE__

  @type budget :: %{
          limit: pos_integer(),
          remaining: non_neg_integer(),
          reset: pos_integer(),
          window: pos_integer()
        }

  def start_link(_opts), do: GenServer.start_link(__MODULE__, nil, name: __MODULE__)

  @spec admit(term(), pos_integer(), pos_integer()) ::
          {:ok, budget()} | {:error, :rate_limited, budget()}
  def admit(key, limit, window_seconds) do
    now = System.monotonic_time(:second)
    bucket = Integer.floor_div(now, window_seconds)
    sweep(window_seconds, bucket)
    row = {window_seconds, key, bucket}
    count = :ets.update_counter(@table, row, {2, 1}, {row, 0})

    budget = %{
      limit: limit,
      remaining: max(limit - count, 0),
      reset: (bucket + 1) * window_seconds - now,
      window: window_seconds
    }

    if count <= limit, do: {:ok, budget}, else: {:error, :rate_limited, budget}
  end

  # The first request of a window drops that window's older counters, and the
  # older sweep markers with them.
  defp sweep(window_seconds, bucket) do
    if :ets.insert_new(@table, {{:swept, window_seconds, bucket}}) do
      :ets.select_delete(@table, [
        {{{window_seconds, :_, :"$1"}, :_}, [{:<, :"$1", bucket}], [true]},
        {{{:swept, window_seconds, :"$1"}}, [{:<, :"$1", bucket}], [true]}
      ])
    end
  end

  @impl true
  def init(nil) do
    :ets.new(@table, [
      :named_table,
      :public,
      :set,
      read_concurrency: true,
      write_concurrency: true
    ])

    {:ok, nil}
  end
end
