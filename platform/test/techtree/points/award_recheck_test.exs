defmodule Techtree.Points.AwardRecheckTest do
  # Invariant: a linked social account earns only if the link is still saved, to
  # the same account, when the award is written. A link removed after Points
  # accepted the offer but before the award ran earns nothing; a link moved to
  # another account meanwhile earns nothing for the first and once for the account
  # that holds it, when its own offer is checked, or at the next start run when
  # that offer was turned away while the first award still waited; a link that
  # stays earns once.
  use ExUnit.Case, async: false

  import Ecto.Query
  require Ash.Query
  alias RegentPoints.{Entry, Event, IntakeWorker, Rejection, StartAwards, Store, Worker}
  alias Techtree.Accounts.VerifiedSession
  alias Techtree.Repo

  setup do
    owner = Ecto.Adapters.SQL.Sandbox.start_owner!(Repo, shared: true)
    starts_at = Application.get_env(:regent_points, :starts_at)
    rules = Application.get_env(:regent_points, :approved_rules)
    Application.put_env(:regent_points, :starts_at, DateTime.add(DateTime.utc_now(), -1, :day))
    Application.put_env(:regent_points, :approved_rules, ["social.x"])

    on_exit(fn ->
      Application.put_env(:regent_points, :starts_at, starts_at)
      Application.put_env(:regent_points, :approved_rules, rules)
      Ecto.Adapters.SQL.Sandbox.stop_owner(owner)
    end)

    did = "did:privy:recheck-" <> Ecto.UUID.generate()
    x = %{provider: :x, subject: "x-" <> Ecto.UUID.generate(), username: "linked"}
    assert {:ok, account, []} = did |> session([x]) |> VerifiedSession.establish()

    # Points' first check accepts the link and queues its award.
    run(offers(), IntakeWorker)
    assert [%{processing_status: :pending}] = events(account.id)
    assert [_award] = awards(account.id)

    %{did: did, x: x, account: account}
  end

  test "a link removed before the award runs earns nothing", %{did: did, account: account} do
    # Signing in with a session that no longer lists X removes the saved link.
    assert {:ok, _account, []} = did |> session([]) |> VerifiedSession.establish()

    account.id |> awards() |> run(Worker)

    assert points(account.id) == []
    assert [%{processing_status: :rejected, reason_code: "award_refused"}] = events(account.id)
  end

  test "a link that stays earns once", %{did: did, x: x, account: account} do
    assert {:ok, _account, []} = did |> session([x]) |> VerifiedSession.establish()

    account.id |> awards() |> run(Worker)

    assert [10_000_000] = points(account.id)
    assert [%{processing_status: :confirmed}] = events(account.id)
  end

  test "a link moved to another account before the award runs earns for the one who holds it",
       %{did: did, x: x, account: account} do
    other_did = "did:privy:recheck-" <> Ecto.UUID.generate()
    assert {:ok, other, []} = other_did |> session([]) |> VerifiedSession.establish()

    # The person signs in without X, then the other person links the same X account.
    assert {:ok, _account, []} = did |> session([]) |> VerifiedSession.establish()
    assert {:ok, _other, []} = other_did |> session([x]) |> VerifiedSession.establish()

    account.id |> awards() |> run(Worker)
    assert [%{processing_status: :rejected, reason_code: "award_refused"}] = events(account.id)
    assert "account_changed" in refusals(x)

    # The other person's offer takes over the refused event and earns once.
    run(offers(), IntakeWorker)
    other.id |> awards() |> run(Worker)

    assert points(account.id) == []
    assert [10_000_000] = points(other.id)
    assert [%{processing_status: :confirmed}] = events(other.id)
    assert events(account.id) == []
  end

  test "a moved link whose offer was turned away while the first award waited earns at the next start run",
       %{did: did, x: x, account: account} do
    other_did = "did:privy:recheck-" <> Ecto.UUID.generate()
    assert {:ok, other, []} = other_did |> session([]) |> VerifiedSession.establish()
    assert {:ok, _account, []} = did |> session([]) |> VerifiedSession.establish()
    assert {:ok, _other, []} = other_did |> session([x]) |> VerifiedSession.establish()

    # The other person's offer is checked while the first award still waits.
    run(offers(), IntakeWorker)
    assert "source_identity_conflict" in refusals(x)
    assert events(other.id) == []

    account.id |> awards() |> run(Worker)
    assert [%{processing_status: :rejected, reason_code: "award_refused"}] = events(account.id)

    assert :ok = StartAwards.perform(%Oban.Job{})
    run(offers(), IntakeWorker)
    other.id |> awards() |> run(Worker)

    assert points(account.id) == []
    assert [10_000_000] = points(other.id)
    assert [%{processing_status: :confirmed}] = events(other.id)
    assert events(account.id) == []
  end

  # Oban's job rows are not Ash records, so the queued jobs are read straight from
  # its table.
  defp offers do
    Repo.all(
      from j in Oban.Job,
        where:
          j.worker == "RegentPoints.IntakeWorker" and j.state == "available" and
            fragment("?->>'rule_id'", j.args) == "social.x"
    )
  end

  defp awards(account_id) do
    events = account_id |> events() |> Enum.map(& &1.id)

    Repo.all(
      from j in Oban.Job,
        where:
          j.worker == "RegentPoints.Worker" and j.state == "available" and
            fragment("?->>'event_id'", j.args) in ^events
    )
  end

  defp run(jobs, worker) do
    for job <- jobs, do: assert(worker.perform(%{job | attempt: 1}) == :ok)

    Repo.update_all(from(j in Oban.Job, where: j.id in ^Enum.map(jobs, & &1.id)),
      set: [state: "completed"]
    )
  end

  defp events(account_id) do
    Ash.Query.filter(Event, account_id == ^account_id and rule_id == "social.x")
    |> Ash.read!(actor: Store.system())
  end

  defp points(account_id) do
    Ash.Query.filter(Entry, account_id == ^account_id and rule_id == "social.x")
    |> Ash.read!(actor: Store.system())
    |> Enum.map(& &1.points_micro_delta)
  end

  defp refusals(%{subject: subject}) do
    Rejection
    |> Ash.read!(actor: Store.system())
    |> Enum.filter(&(&1.source["source_event_key"] == "x:" <> subject))
    |> Enum.map(& &1.reason_code)
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
end
