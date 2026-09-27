defmodule Techtree.Network.WithdrawalRaceTest do
  @moduledoc """
  Invariant: two withdrawals of one entry sent at the same moment append
  exactly one withdrawal event, leave one withdrawal time, and both callers are
  handed the one stored receipt.

  The sandbox would run both on a single connection, where they cannot overlap
  inside Postgres, so this runs them on two real connections outside it and
  removes the rows it wrote when it is done.
  """

  use ExUnit.Case, async: false

  alias Ecto.Adapters.SQL.Sandbox
  alias Techtree.NetworkFixture
  alias Techtree.Repo

  setup do
    {public, _private} = keys = NetworkFixture.key_pair()

    entry =
      Sandbox.unboxed_run(Repo, fn ->
        NetworkFixture.seed_entry(participant_public_key: Base.encode64(public))
      end)

    on_exit(fn ->
      Sandbox.unboxed_run(Repo, fn ->
        id = Ecto.UUID.dump!(entry.id)

        Repo.query!(
          "DELETE FROM #{table("network_publication_events")} WHERE publication_entry_id = $1",
          [id]
        )

        Repo.query!("DELETE FROM #{table("network_publication_entries")} WHERE id = $1", [id])
      end)
    end)

    {:ok, entry: entry, keys: keys}
  end

  test "two withdrawals at once append one event and answer with one receipt", context do
    %{entry: entry, keys: keys} = context
    request = NetworkFixture.withdrawal(entry.bundle_digest, keys)
    parent = self()

    racers =
      for _racer <- 1..2 do
        Task.async(fn ->
          Sandbox.unboxed_run(Repo, fn ->
            send(parent, {:ready, self()})
            receive do: (:go -> NetworkFixture.withdraw(request))
          end)
        end)
      end

    ready = for _racer <- racers, do: receive(do: ({:ready, pid} -> pid))
    Enum.each(ready, &send(&1, :go))

    [{:ok, one, first}, {:ok, two, second}] = Task.await_many(racers, 30_000)

    assert Enum.sort([first, second]) == [:existing, :recorded]
    assert one.withdrawn_at == two.withdrawn_at
    assert is_binary(one.withdrawal_receipt_bytes)
    assert one.withdrawal_receipt_bytes == two.withdrawal_receipt_bytes

    %{rows: [[withdrawals]]} =
      Sandbox.unboxed_run(Repo, fn ->
        Repo.query!(
          "SELECT count(*) FROM #{table("network_publication_events")} " <>
            "WHERE publication_entry_id = $1 AND kind = 'withdrawn'",
          [Ecto.UUID.dump!(entry.id)]
        )
      end)

    assert withdrawals == 1
  end

  defp table(name), do: Repo.default_prefix() <> "." <> name
end
