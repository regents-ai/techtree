defmodule Techtree.Network.RateLimit do
  @moduledoc """
  How often one caller may publish a run.

  Publishing is something a person does when a run finishes, so the honest rate
  is a handful an hour and the limit here is deliberately close to that. It is
  not a defence against a determined attacker — nothing counted per address
  ever is — it is what stops one broken script from filling the log while
  somebody works out what it is doing.

  A fixed window, counted in a table this process owns. It is per node and it
  is not persisted, because a limit that survives a restart would need a store,
  and a store for this would be a larger thing than the problem. Old windows are
  swept rather than left to grow, and the sweep deletes them inside the table
  rather than copying the table out to look at it, so its cost does not grow
  with this process's memory however many callers there have been. Each sweep
  reports how long it took, how many windows it deleted and how many remain, as
  the `[:techtree, :rate_limit, :sweep]` event.

  Who the caller is is decided before the count, by
  `TechtreeWeb.ClientAddress`; this module counts whatever key it is handed.
  """

  use GenServer

  alias Techtree.Network

  @table __MODULE__

  @doc """
  Start the counter table.
  """
  @spec start_link(keyword()) :: GenServer.on_start()
  def start_link(options), do: GenServer.start_link(__MODULE__, options, name: __MODULE__)

  @doc """
  Count one attempt by this caller, and say whether it is allowed.

  Returns `{:error, seconds}` when it is not, naming how long the caller should
  wait before the window turns over.
  """
  @spec allow(term()) :: :ok | {:error, pos_integer()}
  def allow(caller, now \\ System.system_time(:second)) do
    limits = Network.rate_limit()
    window = Keyword.fetch!(limits, :window_seconds)
    limit = Keyword.fetch!(limits, :limit)
    bucket = div(now, window)

    count = :ets.update_counter(@table, {caller, bucket}, {2, 1}, {{caller, bucket}, 0})

    if count <= limit do
      :ok
    else
      {:error, (bucket + 1) * window - now}
    end
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
    window = Keyword.fetch!(Network.rate_limit(), :window_seconds)
    current = div(System.system_time(:second), window)

    {microseconds, deleted} =
      :timer.tc(fn ->
        :ets.select_delete(@table, [{{{:_, :"$1"}, :_}, [{:<, :"$1", current}], [true]}])
      end)

    :telemetry.execute(
      [:techtree, :rate_limit, :sweep],
      %{duration: microseconds, deleted: deleted, size: :ets.info(@table, :size)},
      %{}
    )

    schedule()
    {:noreply, state}
  end

  defp schedule do
    window = Keyword.fetch!(Network.rate_limit(), :window_seconds)
    Process.send_after(self(), :sweep, window * 1000)
  end
end
