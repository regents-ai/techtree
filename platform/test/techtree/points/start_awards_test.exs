defmodule Techtree.Points.StartAwardsTest do
  # Invariant: an account, its linked social account and its paired agent from
  # before the Points start earn their one-time awards at the start, once, through
  # this site's own checks, without the person doing anything.
  use ExUnit.Case, async: false

  import Ecto.Query
  require Ash.Query
  alias RegentPoints.{Entry, Event, IntakeWorker, StartAwards, Store, Worker}
  alias Techtree.Accounts.VerifiedSession
  alias Techtree.Repo

  @rules ["account.activated", "social.x", "agent.activated"]

  setup do
    owner = Ecto.Adapters.SQL.Sandbox.start_owner!(Repo, shared: true)
    starts_at = Application.get_env(:regent_points, :starts_at)
    rules = Application.get_env(:regent_points, :approved_rules)

    on_exit(fn ->
      Application.put_env(:regent_points, :starts_at, starts_at)
      Application.put_env(:regent_points, :approved_rules, rules)
      Ecto.Adapters.SQL.Sandbox.stop_owner(owner)
    end)

    # Before launch nothing is approved: what people do then earns nothing.
    Application.put_env(:regent_points, :starts_at, nil)
    Application.put_env(:regent_points, :approved_rules, [])
  end

  test "what an account had before the start earns once, at the start" do
    did = "did:privy:before-start-" <> Ecto.UUID.generate()
    x = %{provider: :x, subject: "x-" <> Ecto.UUID.generate(), username: "early"}
    assert {:ok, account, []} = did |> session([x]) |> VerifiedSession.establish()

    code = RegentAgents.issue_pairing_code!(actor: %RegentAgents.Person{privy_user_id: did})

    RegentAgents.pair_agent!(code.code, "Early", :codex,
      actor: %RegentAgents.Agent{wallet: wallet()}
    )

    # Their offers were turned down while nothing was approved.
    for rule <- @rules, do: run(offers(rule), IntakeWorker)
    assert points(account.id) == []

    # The account's time is kept to the second, rounded, so it can be up to half
    # a second ahead of the clock.
    Process.sleep(1_000)
    start = DateTime.utc_now()
    Application.put_env(:regent_points, :starts_at, start)
    Application.put_env(:regent_points, :approved_rules, @rules)

    assert :ok = StartAwards.perform(%Oban.Job{})
    for rule <- @rules, do: award(rule, account.id)

    assert [
             {"account.activated", 25_000_000},
             {"agent.activated", 25_000_000},
             {"social.x", 10_000_000}
           ] = points(account.id) |> Enum.map(&{&1.rule_id, &1.points_micro_delta})

    assert Enum.all?(points(account.id), &(DateTime.compare(&1.earned_at, start) == :eq))

    # A later run finds the account already recorded and offers nothing more.
    assert :ok = StartAwards.perform(%Oban.Job{})
    assert Enum.flat_map(@rules, &offers/1) == []
  end

  # Oban's job rows are not Ash records, so the queued offers are read straight
  # from its table.
  defp offers(rule) do
    Repo.all(
      from j in Oban.Job,
        where:
          j.worker == "RegentPoints.IntakeWorker" and j.state == "available" and
            fragment("?->>'rule_id'", j.args) == ^rule
    )
  end

  # Points' check of every offer for the rule, then its award for the account.
  defp award(rule, account_id) do
    rule |> offers() |> run(IntakeWorker)

    events =
      Ash.read!(Ash.Query.filter(Event, account_id == ^account_id), actor: Store.system())
      |> Enum.map(& &1.id)

    # Oban's job rows are not Ash records: the awards queued for these events.
    Repo.all(
      from j in Oban.Job,
        where:
          j.worker == "RegentPoints.Worker" and j.state == "available" and
            fragment("?->>'event_id'", j.args) in ^events
    )
    |> run(Worker)
  end

  defp run(jobs, worker) do
    for job <- jobs, do: assert(worker.perform(%{job | attempt: 1}) == :ok)

    # Oban's job rows are not Ash records: the jobs just run are marked done so a
    # later read of the queue skips them.
    Repo.update_all(from(j in Oban.Job, where: j.id in ^Enum.map(jobs, & &1.id)),
      set: [state: "completed"]
    )
  end

  defp points(account_id) do
    Ash.Query.filter(Entry, account_id == ^account_id)
    |> Ash.Query.sort(rule_id: :asc)
    |> Ash.read!(actor: Store.system())
  end

  defp session(did, linked_socials) do
    wallet = "0x" <> String.slice(Base.encode16(:crypto.hash(:sha, did), case: :lower), 0, 40)

    %RegentPrivy.Session{
      app_id: "test-app",
      session_id: "test-session",
      privy_user_id: did,
      wallet_address: wallet,
      wallet_addresses: [wallet],
      linked_socials: linked_socials,
      issued_at: :erlang.system_time(:second),
      expires_at: :erlang.system_time(:second) + 3600
    }
  end

  defp wallet, do: "0x" <> Base.encode16(:crypto.strong_rand_bytes(20), case: :lower)
end
