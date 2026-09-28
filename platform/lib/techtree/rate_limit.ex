defmodule Techtree.RateLimit do
  @moduledoc """
  How often one caller may use a part of this site in a window of time.

  Two budgets are counted here: publishing a run, which a person does a handful
  of times an hour (`TechtreeWeb.PublicationRate`), and every other request to
  the health check and the API (`TechtreeWeb.Endpoint`). Neither is a defence
  against a determined attacker — nothing counted per address ever is — it is
  what stops one broken script from filling the log or crowding out everybody
  else while somebody works out what it is doing.

  A fixed window, counted in a table this process owns. Counting is one atomic
  update of a public table, so no request waits on this process or on another
  request. It is per node and it is not persisted, because a limit that
  survives a restart would need a store, and a store for this would be a larger
  thing than the problem. Windows that have turned over are swept rather than
  left to grow, and the sweep deletes them inside the table rather than copying
  the table out to look at it, so its cost does not grow with this process's
  memory however many callers there have been. Each sweep reports how long it
  took, how many windows it deleted and how many remain, as the
  `[:techtree, :rate_limit, :sweep]` event.

  Who the caller is is decided before the count, by
  `TechtreeWeb.ClientAddress`; this module counts whatever key it is handed.
  """

  use GenServer

  @table __MODULE__
  @sweep_seconds 60

  @typedoc """
  Where a caller stands: the budget, how many requests remain in it, the whole
  seconds until the window resets, and the window in seconds.
  """
  @type budget :: %{
          limit: pos_integer(),
          remaining: non_neg_integer(),
          reset: pos_integer(),
          window: pos_integer()
        }

  @doc """
  Start the counter table.
  """
  @spec start_link(keyword()) :: GenServer.on_start()
  def start_link(options), do: GenServer.start_link(__MODULE__, options, name: __MODULE__)

  @doc """
  Count one request by `caller` against a budget of `limit` requests every
  `window` seconds, and say whether it is allowed and what is left.
  """
  @spec admit(term(), pos_integer(), pos_integer(), integer()) ::
          {:ok, budget()} | {:error, :rate_limited, budget()}
  def admit(caller, limit, window, now \\ System.system_time(:second)) do
    bucket = div(now, window)
    key = {caller, window, bucket}
    count = :ets.update_counter(@table, key, {2, 1}, {key, 0})

    budget = %{
      limit: limit,
      remaining: max(limit - count, 0),
      reset: (bucket + 1) * window - now,
      window: window
    }

    if count <= limit, do: {:ok, budget}, else: {:error, :rate_limited, budget}
  end

  @impl GenServer
  def init(_options) do
    :ets.new(@table, [:named_table, :public, :set, write_concurrency: true])
    {:ok, %{}, {:continue, :sweep}}
  end

  @impl GenServer
  def handle_continue(:sweep, state) do
    schedule()
    {:noreply, state}
  end

  @impl GenServer
  def handle_info(:sweep, state) do
    now = System.system_time(:second)

    # A window is over once its end, (bucket + 1) * window, is not after now.
    over = [{{{:_, :"$1", :"$2"}, :_}, [{:"=<", {:*, {:+, :"$2", 1}, :"$1"}, now}], [true]}]
    {microseconds, deleted} = :timer.tc(fn -> :ets.select_delete(@table, over) end)

    :telemetry.execute(
      [:techtree, :rate_limit, :sweep],
      %{duration: microseconds, deleted: deleted, size: :ets.info(@table, :size)},
      %{}
    )

    schedule()
    {:noreply, state}
  end

  defp schedule, do: Process.send_after(self(), :sweep, @sweep_seconds * 1000)
end
