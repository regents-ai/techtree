defmodule Techtree.Network.WithdrawalRaceTest do
  @moduledoc """
  Invariant: two withdrawals of one entry sent at the same moment append
  exactly one withdrawal event, leave one withdrawal time, and both callers are
  handed the one stored receipt.

  The sandbox would run both on a single connection, where they cannot overlap
  inside Postgres, so this runs them on two real connections outside it and
  removes the entry and events it wrote when it is done.

  Each racer is a different paired agent, so the race meets on the entry and
  not on one agent's pairing, which each withdrawal locks. The pairings must be
  committed for both connections to see them, so the two people and their
  pairings are fixed: written by the first run in this database and found
  again by every later one, they leave nothing new behind (a pairing written
  for each run would also add a lasting row to the shared pairing history).
  Each racer's row in this site's own agents table is removed afterwards and
  signed in again on the next run.
  """

  use ExUnit.Case, async: false

  alias Ecto.Adapters.SQL.Sandbox
  alias Techtree.NetworkFixture
  alias Techtree.Repo

  @racers [
    {"did:privy:withdrawal-race-1", "0x" <> String.pad_leading("ace1", 40, "0")},
    {"did:privy:withdrawal-race-2", "0x" <> String.pad_leading("ace2", 40, "0")}
  ]

  setup do
    {public, _private} = keys = NetworkFixture.key_pair()

    {entry, agents} =
      Sandbox.unboxed_run(Repo, fn ->
        {NetworkFixture.seed_entry(participant_public_key: Base.encode64(public)),
         Enum.map(@racers, fn {owner, wallet} -> NetworkFixture.paired_agent(owner, wallet) end)}
      end)

    on_exit(fn ->
      Sandbox.unboxed_run(Repo, fn ->
        id = Ecto.UUID.dump!(entry.id)

        Repo.query!(
          "DELETE FROM #{table("network_publication_events")} WHERE publication_entry_id = $1",
          [id]
        )

        Repo.query!("DELETE FROM #{table("network_publication_entries")} WHERE id = $1", [id])
        Enum.each(agents, &remove_agent/1)
      end)
    end)

    {:ok, entry: entry, keys: keys, agents: agents}
  end

  # Each racer's row in this site's own agents table, which sign-in writes again
  # on the next run. Its fixed person and pairing stay, to be found again.
  defp remove_agent(agent),
    do:
      Repo.query!("DELETE FROM #{table("agents")} WHERE id = $1", [
        Ecto.UUID.dump!(agent.agent_id)
      ])

  test "two withdrawals at once append one event and answer with one receipt", context do
    %{entry: entry, keys: keys, agents: agents} = context
    request = NetworkFixture.withdrawal(entry.bundle_digest, keys)
    parent = self()

    racers =
      for agent <- agents do
        Task.async(fn ->
          Sandbox.unboxed_run(Repo, fn ->
            send(parent, {:ready, self()})
            receive do: (:go -> NetworkFixture.withdraw(request, agent))
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
