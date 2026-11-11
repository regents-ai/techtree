defmodule Techtree.Points.SignInMilestonesTest do
  # Invariant: a new account, each social account a person links, and a
  # person's paired agents each earn their one-time award once, in one entry.
  # The offer is made inside the save that earns it, so a save that rolls back
  # offers nothing, and a sign-in that changes nothing offers nothing more.
  use ExUnit.Case, async: false

  import Ecto.Query
  require Ash.Query
  alias RegentPoints.{Entry, Event, IntakeWorker, Store, Worker}
  alias Techtree.{Accounts, Repo}
  alias Techtree.Accounts.VerifiedSession
  alias Techtree.Actors.System

  @rules ["account.activated", "social.x", "agent.activated"]

  setup do
    owner = Ecto.Adapters.SQL.Sandbox.start_owner!(Repo, shared: true)
    starts_at = Application.get_env(:regent_points, :starts_at)
    rules = Application.get_env(:regent_points, :approved_rules)
    Application.put_env(:regent_points, :starts_at, ~U[2020-01-01 00:00:00Z])
    Application.put_env(:regent_points, :approved_rules, @rules)

    on_exit(fn ->
      Application.put_env(:regent_points, :starts_at, starts_at)
      Application.put_env(:regent_points, :approved_rules, rules)
      Ecto.Adapters.SQL.Sandbox.stop_owner(owner)
    end)
  end

  test "a new account earns its activation once, and signing in again offers nothing" do
    did = "did:privy:activated-" <> Ecto.UUID.generate()
    wallet = wallet()

    Repo.transaction(fn ->
      Accounts.register_verified!(did, wallet, [wallet],
        actor: %System{},
        return_notifications?: true
      )

      Repo.rollback(:undone)
    end)

    assert offers("account.activated") == []

    account = Accounts.register_verified!(did, wallet, [wallet], actor: %System{})
    assert Accounts.register_verified!(did, wallet, [wallet], actor: %System{}).id == account.id

    assert [offer] = offers("account.activated")
    assert offer.args["source_event_key"] == to_string(account.id)

    # The account's time is kept to the second, rounded, so it can be up to
    # half a second ahead; Points' check waits for it.
    Process.sleep(1_000)
    award("account.activated", account.id)
    assert [25_000_000] = points(account.id)
  end

  test "a linked social account earns once; signing in with it again refreshes it" do
    did = "did:privy:social-" <> Ecto.UUID.generate()
    x = %{provider: :x, subject: "x-" <> Ecto.UUID.generate(), username: "first"}

    assert {:ok, account, []} = did |> session([x]) |> VerifiedSession.establish()

    assert {:ok, _account, []} =
             did |> session([%{x | username: "renamed"}]) |> VerifiedSession.establish()

    assert {:ok, %{username: "renamed", inserted_at: linked_at}} =
             Accounts.get_linked_identity_by_subject(:x, x.subject, actor: %System{})

    assert [_offer] = offers("social.x")

    other = %{x | subject: "x-" <> Ecto.UUID.generate()}
    assert {:ok, _account, []} = did |> session([other]) |> VerifiedSession.establish()
    assert length(offers("social.x")) == 2

    assert {:ok, %{inserted_at: relinked_at}} =
             Accounts.get_linked_identity_by_subject(:x, other.subject, actor: %System{})

    assert DateTime.after?(relinked_at, linked_at)

    Repo.transaction(fn ->
      Accounts.upsert_linked_identity!(
        %{
          provider: :x,
          subject: "x-" <> Ecto.UUID.generate(),
          verified_at: DateTime.utc_now(),
          metadata: %{},
          human_account_id: account.id
        },
        actor: %System{},
        return_notifications?: true
      )

      Repo.rollback(:undone)
    end)

    assert length(offers("social.x")) == 2

    award("social.x", account.id)
    assert [10_000_000] = points(account.id, "social.x")
  end

  test "a person's paired agents earn the first-agent award once" do
    did = "did:privy:paired-" <> Ecto.UUID.generate()
    wallet = wallet()
    account = Accounts.register_verified!(did, wallet, [wallet], actor: %System{})

    agents =
      for name <- ["First", "Second"] do
        code = RegentAgents.issue_pairing_code!(actor: %RegentAgents.Person{privy_user_id: did})

        RegentAgents.pair_agent!(code.code, name, :codex,
          actor: %RegentAgents.Agent{wallet: wallet()}
        )
      end

    assert length(offers("agent.activated")) == 2

    award("agent.activated", account.id)
    assert [25_000_000] = points(account.id, "agent.activated")

    # The award's agent is a paired wallet, and the Points page names it.
    assert [%{actor_id: wallet}] =
             Ash.Query.filter(Entry, account_id == ^account.id and rule_id == "agent.activated")
             |> Ash.read!(actor: Store.system())

    assert %{name: name} = Enum.find(agents, &(&1.wallet == wallet))
    assert {:ok, %{^wallet => ^name}} = Techtree.Points.Accounts.agent_names(account.id, [wallet])
  end

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

    Repo.update_all(from(j in Oban.Job, where: j.id in ^Enum.map(jobs, & &1.id)),
      set: [state: "completed"]
    )
  end

  defp points(account_id, rule \\ "account.activated") do
    Ash.Query.filter(Entry, account_id == ^account_id and rule_id == ^rule)
    |> Ash.read!(actor: Store.system())
    |> Enum.map(& &1.points_micro_delta)
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
