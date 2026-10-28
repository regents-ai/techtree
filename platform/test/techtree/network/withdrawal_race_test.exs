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
  agents are fixed: written by the first run in this database and found again
  by every later one, they leave nothing new behind (a pairing written for each
  run would also add a lasting row to the shared pairing history).
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

    {entry, actors} =
      Sandbox.unboxed_run(Repo, fn ->
        entry = NetworkFixture.seed_entry(participant_public_key: Base.encode64(public))
        {entry, Enum.map(@racers, &kept_agent/1)}
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

    {:ok, entry: entry, keys: keys, actors: actors}
  end

  test "two withdrawals at once append one event and answer with one receipt", context do
    %{entry: entry, keys: keys, actors: actors} = context
    request = NetworkFixture.withdrawal(entry.bundle_digest, keys)
    parent = self()

    racers =
      for actor <- actors do
        Task.async(fn ->
          Sandbox.unboxed_run(Repo, fn ->
            send(parent, {:ready, self()})
            receive do: (:go -> NetworkFixture.withdraw(request, actor))
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

  # One person and their agent, where Regents writes them (as
  # NetworkFixture.paired_agent/0 does), written only if they are not there yet.
  defp kept_agent({owner, wallet}) do
    Repo.query!(
      """
      INSERT INTO regent_names.platform_human_users
        (privy_user_id, wallet_address, wallet_addresses, created_at, updated_at)
      VALUES ($1, $2::varchar, ARRAY[$2::varchar], now(), now())
      ON CONFLICT (privy_user_id) DO NOTHING
      """,
      [owner, wallet]
    )

    Repo.query!(
      """
      INSERT INTO regent_agents.paired_agents
        (privy_user_id, wallet, name, harness, paired_at, last_contact_at)
      VALUES ($1, $2, 'Probe', 'Hermes Agent', now(), now())
      ON CONFLICT (wallet) DO NOTHING
      """,
      [owner, wallet]
    )

    %{rows: [[id]]} =
      Repo.query!(
        "SELECT id FROM regent_agents.paired_agents WHERE privy_user_id = $1 AND wallet = $2",
        [owner, wallet]
      )

    %{id: Ecto.UUID.load!(id), privy_user_id: owner, wallet: wallet}
  end

  defp table(name), do: Repo.default_prefix() <> "." <> name
end
