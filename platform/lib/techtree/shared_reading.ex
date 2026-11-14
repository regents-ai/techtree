defmodule Techtree.SharedReading do
  @moduledoc """
  A figure every reader it admits sees alike, read once and shared by every open
  page.

  It is for a reading built from many rows, such as the Points board. A public row
  saved through Ash reaches pages through its own `pub_sub` publication instead,
  and anything that differs by viewer is reread under that viewer's scope: neither
  belongs here.
  The rule and its reasons are in the `ash-frontend` skill,
  `references/public-figures.md`.

  One producer owns each key and calls `put/2` when it has a reading, or
  `degraded/1` when it could not get one. A page calls `subscribe/1`, then
  `fetch/1`, and on each `{:shared_reading, key}` it fetches again:

      def mount(_params, _session, socket) do
        key = Techtree.Points.Board.key()
        if connected?(socket), do: Techtree.SharedReading.subscribe(key)
        {:ok, assign(socket, board: Techtree.SharedReading.fetch(key))}
      end

      def handle_info({:shared_reading, key}, socket),
        do: {:noreply, assign(socket, board: Techtree.SharedReading.fetch(key))}

  Pages are woken only when the reading or its `degraded?` mark differs from the
  one held; `at`, the moment it was last read, moves without waking anyone. A
  wake-up reaches this machine's pages only, because each machine keeps its own
  table and runs its own producers.

  A reading never disables or delays an on-chain button. Stale, degraded or
  absent, every button stays live; only the chain's own state at the latest
  block, read for that press, may block one.

  ## Kinds

  A key is `{kind, id}`. `kind` is one of `@kinds` and `id` is an integer or a
  short string the site already holds in its own rows or settings, never text
  from a request. Each kind states who may see it and why, the most keys it may
  hold and the largest reading it accepts, so adding one is a reviewed change.
  Nothing hands out a reading by its kind: each page or answer fetches the keys it
  shows, and shows a kind only to the readers its `audience` names. A reading is small plain data: numbers, strings, atoms, dates,
  `Decimal`s, and maps, lists or tuples of them. An Ash record or any other
  struct is refused, as is a reading over its kind's size.

  Every kind also states `within`: the seconds inside which a working producer
  reads each of its keys again, whether or not anything changed. A producer that
  rereads on notice does so when `heal/1` asks, each minute (`Techtree.SharedReading.Heal`),
  which is also what mends a notice that was lost. A key older than its kind's
  `within` is late, whatever the kind.

  ## Measurements

  `measure/0` runs with the site's other periodic measurements and reports, for
  each kind, how many keys it holds, how many of them have never been read, how
  many are late and how long ago its oldest reading was taken
  (`[:techtree, :shared_reading, :kind]`), and the table's size in memory
  (`[:techtree, :shared_reading, :table]`). Every reading offered to `put/2`
  reports its `bytes` and its kind's `limit` (`[:techtree, :shared_reading, :size]`),
  so a reading growing towards its limit shows before it is refused. Every `degraded/1` is counted
  (`[:techtree, :shared_reading, :degraded]`), as is every refused reading
  (`[:techtree, :shared_reading, :refused]`) and every wake-up sent to pages
  (`[:techtree, :shared_reading, :woken]`), by kind.
  """

  use GenServer

  @table __MODULE__

  # audience: who may see it, and why. keys: the most this kind holds.
  # bytes: the largest reading, measured as `:erlang.external_size/1`.
  # within: the seconds inside which a working producer reads every key again.
  @kinds %{
    # Ten rows, however many accounts have points: with a 1 KB name, a 2.3 KB
    # square pattern, a 1 KB picture address and an ENS name each, ten rows
    # measure about 48 KB (ash-template's docs/points-foundation.md).
    points_board: %{
      audience:
        "signed-in people and paired agents, the readers the Points page and the agent's " <>
          "Points answer admit; each gets the rows without account ids " <>
          "(Techtree.Points.Board)",
      keys: 1,
      bytes: 65_536,
      within: 150
    }
  }

  @type key :: {kind :: atom(), id :: integer() | String.t()}
  @type entry :: %{reading: term(), at: DateTime.t() | nil, degraded?: boolean()}

  def start_link(_opts), do: GenServer.start_link(__MODULE__, nil, name: __MODULE__)

  @doc "The reading held for `key`, or `:error` while there is none."
  @spec fetch(key()) :: {:ok, entry()} | :error
  def fetch({kind, id} = key)
      when is_map_key(@kinds, kind) and (is_integer(id) or is_binary(id)) do
    case :ets.lookup(@table, key) do
      [{^key, entry}] -> {:ok, entry}
      [] -> :error
    end
  rescue
    # No table for the instant its owner restarts: the same as no reading.
    ArgumentError -> :error
  end

  @doc "Hear `{:shared_reading, key}` whenever the reading for `key` changes."
  @spec subscribe(key()) :: :ok
  def subscribe(key), do: Phoenix.PubSub.subscribe(Techtree.PubSub, topic(checked(key)))

  @doc "Stops hearing `key`, for a page that stays open and no longer shows it."
  @spec unsubscribe(key()) :: :ok
  def unsubscribe(key), do: Phoenix.PubSub.unsubscribe(Techtree.PubSub, topic(checked(key)))

  @doc """
  Stores `reading` as read just now. Answers `{:error, :too_large}`,
  `{:error, :not_plain}` or `{:error, :too_many_keys}` when it is refused; the
  reading held before then stays.
  """
  @spec put(key(), term()) :: :ok | {:error, :too_large | :not_plain | :too_many_keys}
  def put(key, reading) do
    {kind, _id} = checked(key)

    # Checked here, in the producer, so a reading that cannot be checked fails
    # its producer and never the table's owner.
    with :ok <- fits(kind, reading) do
      GenServer.call(__MODULE__, {:put, key, reading})
    end
    |> counted(kind)
  end

  @doc """
  Marks `key` as not read this time. The last reading stays, marked `degraded?`;
  a key that never had one holds `reading: nil`.
  """
  @spec degraded(key()) :: :ok | {:error, :too_many_keys}
  def degraded(key) do
    {kind, _id} = checked(key)
    counted(GenServer.call(__MODULE__, {:degraded, key}), kind)
  end

  @doc """
  Asks the producer of `kind`, on every machine, to read all its keys again.
  The producer hears `{:shared_reading_heal, kind}` after `subscribe_heal/1`.
  """
  @spec heal(atom()) :: :ok
  def heal(kind) when is_map_key(@kinds, kind) do
    Phoenix.PubSub.broadcast(Techtree.PubSub, heal_topic(kind), {:shared_reading_heal, kind})
  end

  @spec subscribe_heal(atom()) :: :ok
  def subscribe_heal(kind) when is_map_key(@kinds, kind),
    do: Phoenix.PubSub.subscribe(Techtree.PubSub, heal_topic(kind))

  @doc "Forgets `key`, when the row or setting it stood for has ended."
  @spec delete(key()) :: :ok
  def delete(key), do: GenServer.call(__MODULE__, {:delete, checked(key)})

  @doc """
  The ids of every key held for `kind`. A producer whose keys come and go reads
  this on each pass and deletes the ones its fresh read no longer has, so it
  keeps no list of its own, and a restart of the producer alone leaves no key
  behind.

  It is for a producer's pass only, never a page's mount or each event: it walks
  the whole table. Never count with it either: it answers `[]` in the instant
  the table's owner restarts, which a measurement would show as a healthy zero.
  """
  @spec ids(atom()) :: [integer() | String.t()]
  def ids(kind) when is_map_key(@kinds, kind) do
    :ets.select(@table, [{{{kind, :"$1"}, :_}, [], [:"$1"]}])
  rescue
    # No table for the instant its owner restarts: nothing is held.
    ArgumentError -> []
  end

  @doc false
  def measure do
    now = DateTime.utc_now()

    # Each key's kind and when it was read; the readings themselves stay put.
    held =
      @table
      |> :ets.select([{{{:"$1", :_}, %{at: :"$2"}}, [], [{{:"$1", :"$2"}}]}])
      |> Enum.group_by(&elem(&1, 0), &elem(&1, 1))

    # Every kind each tick, so a kind whose keys are all gone reads 0.
    for {kind, %{within: within}} <- @kinds do
      ats = Map.get(held, kind, [])
      read = for %DateTime{} = at <- ats, do: DateTime.diff(now, at, :millisecond)

      :telemetry.execute(
        [:techtree, :shared_reading, :kind],
        %{
          keys: length(ats),
          never_read: length(ats) - length(read),
          late: Enum.count(read, &(&1 > within * 1_000)),
          oldest_seconds: Enum.max(read, fn -> 0 end) / 1_000
        },
        %{kind: kind}
      )
    end

    :telemetry.execute(
      [:techtree, :shared_reading, :table],
      %{bytes: :ets.info(@table, :memory) * :erlang.system_info(:wordsize)},
      %{}
    )
  rescue
    # The poller drops a measurement that raises for good. No table for the
    # instant its owner restarts, which can fall between the two reads above
    # (the size then reads :undefined): skip this tick.
    [ArgumentError, ArithmeticError] -> :ok
  end

  @impl true
  def init(nil) do
    :ets.new(@table, [:named_table, :protected, read_concurrency: true])
    {:ok, nil}
  end

  @impl true
  def handle_call({:put, key, reading}, _from, state) do
    held = held(key)

    reply =
      with :ok <- room(key, held),
           do: store(key, held, %{reading: reading, at: DateTime.utc_now(), degraded?: false})

    {:reply, reply, state}
  end

  def handle_call({:degraded, {kind, _id} = key}, _from, state) do
    held = held(key)
    :telemetry.execute([:techtree, :shared_reading, :degraded], %{count: 1}, %{kind: kind})

    reply =
      with :ok <- room(key, held),
           do: store(key, held, Map.put(held || %{reading: nil, at: nil}, :degraded?, true))

    {:reply, reply, state}
  end

  def handle_call({:delete, key}, _from, state) do
    if :ets.member(@table, key) do
      :ets.delete(@table, key)
      wake(key)
    end

    {:reply, :ok, state}
  end

  defp held(key) do
    case :ets.lookup(@table, key) do
      [{^key, entry}] -> entry
      [] -> nil
    end
  end

  # Stored first, so a page woken by it reads the new entry.
  defp store(key, held, entry) do
    :ets.insert(@table, {key, entry})
    if changed?(held, entry), do: wake(key)
    :ok
  end

  defp changed?(nil, _entry), do: true

  defp changed?(held, entry),
    do: held.reading != entry.reading or held.degraded? != entry.degraded?

  defp wake({kind, _id} = key) do
    :telemetry.execute([:techtree, :shared_reading, :woken], %{count: 1}, %{kind: kind})
    Phoenix.PubSub.local_broadcast(Techtree.PubSub, topic(key), {:shared_reading, key})
  end

  defp topic({kind, id}), do: "shared_reading:#{kind}:#{id}"
  defp heal_topic(kind), do: "shared_reading_heal:#{kind}"

  defp counted(:ok, _kind), do: :ok

  defp counted({:error, reason} = refused, kind) do
    :telemetry.execute([:techtree, :shared_reading, :refused], %{count: 1}, %{
      kind: kind,
      reason: reason
    })

    refused
  end

  # Every offered reading's size is reported against its kind's limit, so one
  # that grows shows nearing the limit well before it is refused.
  defp fits(kind, reading) do
    bytes = :erlang.external_size(reading)
    limit = @kinds[kind].bytes

    :telemetry.execute(
      [:techtree, :shared_reading, :size],
      %{bytes: bytes, limit: limit},
      %{kind: kind}
    )

    cond do
      bytes > limit -> {:error, :too_large}
      not plain?(reading) -> {:error, :not_plain}
      true -> :ok
    end
  end

  defp room(_key, %{}), do: :ok

  defp room({kind, _id}, nil) do
    if :ets.select_count(@table, [{{{kind, :_}, :_}, [], [true]}]) < @kinds[kind].keys,
      do: :ok,
      else: {:error, :too_many_keys}
  end

  defp plain?(%module{}), do: module in [DateTime, Date, Decimal]

  defp plain?(map) when is_map(map),
    do: Enum.all?(map, fn {key, value} -> plain?(key) and plain?(value) end)

  defp plain?([]), do: true
  defp plain?([head | tail]), do: plain?(head) and plain?(tail)
  defp plain?(tuple) when is_tuple(tuple), do: tuple |> Tuple.to_list() |> plain?()
  defp plain?(term), do: is_number(term) or is_binary(term) or is_atom(term)

  # A key is built by site code from a fixed kind and an id the site holds.
  defp checked({kind, id} = key)
       when is_map_key(@kinds, kind) and (is_integer(id) or is_binary(id)),
       do: key
end
