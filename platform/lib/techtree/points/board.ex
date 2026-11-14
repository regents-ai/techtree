defmodule Techtree.Points.Board do
  @moduledoc """
  The Points board every signed-in reader shares (`RegentPoints.leaderboard/1`),
  read once for all of them and held in `Techtree.SharedReading` under `key/0`.
  One runs on each machine.

  This is a reread on notice, the second of the two shapes the `elixir-stack`
  skill lets keep a shared reading. It hears every award, correction and period
  bonus on this site (`points:board`) and reads the board again, at most once a
  second however many arrive. It holds nothing but whether a read is due: no
  queue, no copy of rows, and it never writes the database.

  An award on another Regent site changes the shared totals without a notice
  here, and a notice can be lost, so each minute `Techtree.SharedReading.Heal`
  asks for the board to be read again; that also keeps the reading inside its
  kind's `within`.

  The reading holds the ten highest rows with their account ids. Pages and the
  agent's answer keep the ids on the server: a reader gets the rows without ids
  and a mark on their own row, and their own place comes with their own summary
  (`TechtreeWeb.PointsEntries`). A board too large for its kind is refused and
  marked degraded, and the last one stays shown as behind.

  The first read happens as it starts, so the key holds a reading or its
  degraded mark before the site serves a page.
  """

  use GenServer

  alias Techtree.SharedReading

  @kind :points_board

  @doc "Where the board of this site's Points program is held."
  def key, do: {@kind, RegentPoints.Rules.program()}

  def start_link(_opts), do: GenServer.start_link(__MODULE__, nil)

  @impl true
  def init(nil) do
    SharedReading.subscribe_heal(@kind)
    Phoenix.PubSub.subscribe(Techtree.PubSub, "points:board")
    read()
    {:ok, false}
  end

  @impl true
  def handle_info(%{topic: "points:board"}, due?), do: {:noreply, due(due?)}
  def handle_info({:shared_reading_heal, @kind}, due?), do: {:noreply, due(due?)}

  def handle_info(:read, true) do
    read()
    {:noreply, false}
  end

  @doc "Reads the board now and holds it, or marks it not read."
  def read do
    with {:ok, board} <- board(),
         :ok <- SharedReading.put(key(), board) do
      :ok
    else
      {:error, _not_held} -> SharedReading.degraded(key())
    end
  end

  # The first notice starts the one-second wait; the rest join it.
  defp due(true), do: true

  defp due(false) do
    Process.send_after(self(), :read, 1_000)
    true
  end

  defp board do
    RegentPoints.leaderboard(actor: RegentPoints.Store.system())
  rescue
    # The database not answering raises beneath Ash. It is a read not taken,
    # never a reason for this process, and the site with it, to stop.
    error in [DBConnection.ConnectionError, Postgrex.Error] -> {:error, error}
  end
end
