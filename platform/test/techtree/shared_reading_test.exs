defmodule Techtree.SharedReadingTest do
  # Invariants of the figure every reader it admits sees alike, as all five sites
  # copy it from the template: a bad reading never replaces a good one, a failed
  # first read is visible, a reading that has not changed wakes no page, the kind
  # holds no more keys than it states, and measuring survives the table being
  # away. Stops the table's owner, so it never runs beside another test.
  use ExUnit.Case, async: false

  alias Techtree.Points.Board
  alias Techtree.SharedReading

  @limit 65_536

  setup do
    SharedReading.delete(Board.key())
    on_exit(fn -> SharedReading.delete(Board.key()) end)
  end

  test "a refused reading keeps the one held" do
    assert :ok = SharedReading.put(Board.key(), 41)
    assert {:ok, %{at: at}} = SharedReading.fetch(Board.key())

    assert {:error, :too_large} =
             SharedReading.put(Board.key(), String.duplicate("9", @limit + 1))

    assert {:error, :not_plain} = SharedReading.put(Board.key(), 1..2)

    assert {:ok, %{reading: 41, at: ^at, degraded?: false}} = SharedReading.fetch(Board.key())
  end

  test "every reading offered reports its size against its kind's limit, refused ones too" do
    test = self()

    :telemetry.attach(
      "shared-reading-size-test",
      [:techtree, :shared_reading, :size],
      fn _, size, %{kind: kind}, _ -> send(test, {kind, size}) end,
      nil
    )

    on_exit(fn -> :telemetry.detach("shared-reading-size-test") end)

    assert :ok = SharedReading.put(Board.key(), 41)

    assert {:error, :too_large} =
             SharedReading.put(Board.key(), String.duplicate("9", @limit + 1))

    assert_received {:points_board, %{bytes: small, limit: @limit}} when small <= @limit
    assert_received {:points_board, %{bytes: large, limit: @limit}} when large > @limit
  end

  test "a first read that fails is marked, and pages hear it" do
    key = Board.key()
    SharedReading.subscribe(key)

    assert :ok = SharedReading.degraded(key)

    assert_receive {:shared_reading, ^key}
    assert {:ok, %{reading: nil, at: nil, degraded?: true}} = SharedReading.fetch(key)
  end

  test "a reading read again unchanged wakes no page; a failed read does" do
    key = Board.key()
    assert :ok = SharedReading.put(key, 41)
    SharedReading.subscribe(key)

    assert :ok = SharedReading.put(key, 41)
    refute_receive {:shared_reading, ^key}, 50

    assert :ok = SharedReading.degraded(key)
    assert_receive {:shared_reading, ^key}
    assert {:ok, %{reading: 41, degraded?: true}} = SharedReading.fetch(key)
  end

  test "the board kind holds one key" do
    assert :ok = SharedReading.put(Board.key(), 41)
    assert {:error, :too_many_keys} = SharedReading.put({:points_board, "another"}, 7)
    assert :error = SharedReading.fetch({:points_board, "another"})
  end

  test "a measurement taken while the table is away is skipped, and measuring carries on" do
    test = self()
    event = [:techtree, :shared_reading, :table]

    :telemetry.attach(
      "shared-reading-test",
      event,
      fn _, bytes, _, _ -> send(test, bytes) end,
      nil
    )

    on_exit(fn ->
      :telemetry.detach("shared-reading-test")
      Supervisor.restart_child(Techtree.Supervisor, SharedReading)
    end)

    :ok = Supervisor.terminate_child(Techtree.Supervisor, SharedReading)

    assert :ok = SharedReading.measure()
    refute_received %{bytes: _}
    assert :error = SharedReading.fetch(Board.key())

    {:ok, _owner} = Supervisor.restart_child(Techtree.Supervisor, SharedReading)

    SharedReading.measure()
    assert_received %{bytes: bytes} when bytes > 0
  end
end
