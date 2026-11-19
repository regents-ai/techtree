defmodule Techtree.Points.StartAwardsTest do
  # Invariant: an account, its linked social account and its paired agent from
  # before the Points start earn their one-time awards at the start, once, through
  # this site's own checks, without the person doing anything; those from after
  # the start that Points has not recorded earn them once, at their own time.
  use ExUnit.Case, async: false

  import Ecto.Query
  require Ash.Query
  alias RegentPoints.{Entry, Event, IntakeWorker, StartAwards, Store, Worker}
  alias Techtree.Accounts
  alias Techtree.Accounts.VerifiedSession
  alias Techtree.Actors.System
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

  test "what an account did after the start, before the site switched Points on, earns once, at its own time" do
    early_did = "did:privy:before-start-" <> Ecto.UUID.generate()
    assert {:ok, early, []} = early_did |> session([]) |> VerifiedSession.establish()

    # Points has started, but this site has not switched it on yet.
    Process.sleep(1_000)
    start = DateTime.utc_now()
    Application.put_env(:regent_points, :starts_at, start)
    Process.sleep(1_000)

    did = "did:privy:after-start-" <> Ecto.UUID.generate()
    x = %{provider: :x, subject: "x-" <> Ecto.UUID.generate(), username: "late"}
    assert {:ok, account, []} = did |> session([x]) |> VerifiedSession.establish()

    code = RegentAgents.issue_pairing_code!(actor: %RegentAgents.Person{privy_user_id: did})

    RegentAgents.pair_agent!(code.code, "Late", :codex,
      actor: %RegentAgents.Agent{wallet: wallet()}
    )

    # Their offers were turned down while the site had nothing approved.
    for rule <- @rules, do: run(offers(rule), IntakeWorker)
    assert points(early.id) == []
    assert points(account.id) == []

    # The account's time can be up to half a second ahead of the clock.
    Process.sleep(1_000)
    Application.put_env(:regent_points, :approved_rules, @rules)

    assert :ok = StartAwards.perform(%Oban.Job{})
    for id <- [early.id, account.id], rule <- @rules, do: award(rule, id)

    # The account from before the start still earns at the start.
    assert [%{rule_id: "account.activated", earned_at: early_at}] = points(early.id)
    assert DateTime.compare(early_at, start) == :eq

    assert [
             {"account.activated", 25_000_000, created_at},
             {"agent.activated", 25_000_000, paired_at},
             {"social.x", 10_000_000, linked_at}
           ] = points(account.id) |> Enum.map(&{&1.rule_id, &1.points_micro_delta, &1.earned_at})

    {:ok, saved} = Accounts.points_account(account.id, actor: %System{})
    {:ok, link} = Accounts.get_linked_identity_by_subject(:x, x.subject, actor: %System{})
    {:ok, [pairing]} = RegentAgents.pairing_histories(did)

    for {earned_at, done_at} <- [
          {created_at, saved.created_at},
          {paired_at, pairing.paired_at},
          {linked_at, link.inserted_at}
        ] do
      assert DateTime.after?(earned_at, start)
      assert DateTime.compare(earned_at, done_at) == :eq
    end

    # A later run finds both accounts already recorded and offers nothing more.
    assert :ok = StartAwards.perform(%Oban.Job{})
    assert Enum.flat_map(@rules, &offers/1) == []
    assert length(points(early.id)) == 1
    assert length(points(account.id)) == 3
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
