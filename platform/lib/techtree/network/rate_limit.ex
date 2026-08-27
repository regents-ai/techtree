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
  swept rather than left to grow.

  The caller is identified by the address the connection came from, which is
  what this application can actually see. It does not read a forwarding header,
  because a header is written by whoever is upstream and trusting one that has
  not been proven to come from a proxy this deployment controls is how a per-
  caller limit becomes no limit at all.
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

    for {{_caller, bucket} = key, _count} <- :ets.tab2list(@table), bucket < current do
      :ets.delete(@table, key)
    end

    schedule()
    {:noreply, state}
  end

  defp schedule do
    window = Keyword.fetch!(Network.rate_limit(), :window_seconds)
    Process.send_after(self(), :sweep, window * 1000)
  end
end
