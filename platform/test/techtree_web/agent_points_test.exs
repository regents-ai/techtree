defmodule TechtreeWeb.AgentPointsTest do
  # What a paired agent reads of its person's Points: their own figures, the
  # actions still open, and the leaderboard with their own row marked beside other
  # people's names or wallets. Awards are earned the way the site earns them: an
  # account is made, and the queued checks are run. The board every reader shares
  # is then read once, as its producer reads it on notice.
  use ExUnit.Case, async: false

  import Phoenix.ConnTest

  alias Techtree.{Accounts, NetworkFixture, SharedReading}
  alias Techtree.Accounts.VerifiedSession
  alias Techtree.Actors.System
  alias Techtree.Points.Board

  @endpoint TechtreeWeb.Endpoint
  @wallet "0x" <> String.duplicate("b", 40)
  @other "0x" <> String.duplicate("9", 40)

  setup do
    owner = Ecto.Adapters.SQL.Sandbox.start_owner!(Techtree.Repo, shared: true)

    previous =
      Map.new([:starts_at, :approved_rules], &{&1, Application.get_env(:regent_points, &1)})

    Application.put_env(:regent_points, :starts_at, DateTime.add(DateTime.utc_now(), -1, :day))
    Application.put_env(:regent_points, :approved_rules, ~w(account.activated social.x))

    on_exit(fn ->
      Enum.each(previous, fn {key, value} -> Application.put_env(:regent_points, key, value) end)
      SharedReading.delete(Board.key())
      Ecto.Adapters.SQL.Sandbox.stop_owner(owner)
    end)

    Accounts.register_verified!("did:privy:agent-points-other", @other, [@other],
      actor: %System{}
    )

    {:ok, account, []} =
      VerifiedSession.establish(%RegentPrivy.Session{
        app_id: "test-app",
        session_id: "agent-points",
        privy_user_id: "did:privy:agent-points",
        wallet_address: @wallet,
        wallet_addresses: [@wallet],
        linked_socials: [],
        issued_at: :os.system_time(:second),
        expires_at: :os.system_time(:second) + 3600
      })

    # The account's time is kept to the second, rounded, so it can be up to half a
    # second ahead; Points' check waits for it.
    Process.sleep(1_000)
    assert %{failure: 0} = Oban.drain_queue(queue: :points, with_recursion: true)
    assert :ok = Board.read()

    %{person: account}
  end

  # The person's own figures, the actions still open, and a leaderboard whose rows
  # carry a place, a name or wallet and a total each, and nothing else.
  test "a paired agent reads its person's figures, open actions and place", %{person: person} do
    answer = person |> agent_points() |> json_response(200)

    assert answer["points"] == "25"
    assert answer["rank"] == 1
    assert answer["earned_today"] == "25"

    assert %{"done" => true, "left" => false} =
             Enum.find(answer["to_do"], &(&1["label"] == "Account activated"))

    assert %{"done" => false, "left" => true} =
             Enum.find(answer["to_do"], &(&1["label"] == "X account linked"))

    # Two accounts level on points share first place; only the person's row is
    # marked. Other tests' awards commit on purpose and sit below them.
    assert answer["leaderboard"] |> Enum.take(2) |> Enum.map(& &1["rank"]) == [1, 1]
    assert Enum.count(answer["leaderboard"], & &1["you"]) == 1

    for row <- answer["leaderboard"] do
      assert row |> Map.keys() |> Enum.sort() == ~w(ens_name name points rank wallet you)
    end

    assert %{"name" => nil, "ens_name" => nil, "you" => false} =
             Enum.find(answer["leaderboard"], &(&1["wallet"] == @other))
  end

  # The agent gets no half answer while the shared board is not read.
  test "while the board is not read, the agent's whole answer is unavailable", %{person: person} do
    SharedReading.delete(Board.key())

    assert %{"error" => %{"code" => "unavailable"}} =
             person |> agent_points() |> json_response(503)
  end

  # Pairs an agent with the person and asks for Points as that agent; the sign-in
  # service's check of the agent's signature is answered by the fixture.
  defp agent_points(person) do
    NetworkFixture.sign_as(%{wallet_address: @wallet})

    code =
      RegentAgents.issue_pairing_code!(
        actor: %RegentAgents.Person{privy_user_id: person.privy_user_id}
      )

    RegentAgents.pair_agent!(code.code, "Fixture", :codex,
      actor: %RegentAgents.Agent{wallet: @wallet}
    )

    build_conn()
    |> NetworkFixture.signed()
    |> get("/api/v1/account/points")
  end
end
