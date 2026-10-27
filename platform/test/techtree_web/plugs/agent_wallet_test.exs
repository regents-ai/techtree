defmodule TechtreeWeb.Plugs.AgentWalletTest do
  @moduledoc """
  The three addresses a signed agent uses (publications, Model Climb reports and
  `/tools/account`), requested the way an agent sends them. Only the sign-in
  service's verdict is a stand-in (`NetworkFixture.sign_as/1`); the agent record,
  the pairing and the person's account are the site's own.
  """

  use TechtreeWeb.ConnCase, async: false

  require Ash.Query

  alias Ecto.Adapters.SQL
  alias Techtree.Agents.Agent
  alias Techtree.NetworkFixture
  alias Techtree.Repo
  alias TechtreeWeb.Plugs.AgentWallet

  # One request per door. The publication body is no document, so an admitted
  # agent meets the publication address's own refusal instead of a sign-in one.
  @doors [
    {:post, "/api/v1/publications", "{}"},
    {:get, "/api/model-climb/v1/reports", nil},
    {:get, "/tools/account/balances", nil}
  ]

  setup %{conn: conn} do
    # The request budget is counted per caller, so each test is its own caller.
    {:ok,
     conn:
       Map.put(conn, :remote_ip, {198, 18, 0, rem(System.unique_integer([:positive]), 254) + 1})}
  end

  test "an unsigned request is refused at every door, and adds no agent", %{conn: conn} do
    wallet = wallet()
    NetworkFixture.sign_as(%{wallet_address: wallet})

    for door <- @doors do
      refused = send_to(conn, door, signed?: false)

      assert %{"code" => _, "message" => _, "hint" => _} =
               json_response(refused, 401)["error"]
    end

    assert agents(wallet) == []
  end

  test "an agent nobody paired is refused at every door as itself, and is known by its wallet",
       %{conn: conn} do
    wallet = wallet()
    NetworkFixture.sign_as(%{wallet_address: wallet})

    seen =
      for door <- @doors do
        assert error_code(send_to(conn, door), 403) == "agent_not_paired"
        [%Agent{last_seen_at: seen}] = agents(wallet)
        seen
      end

    # One record for the wallet, seen again on each request.
    assert seen == Enum.sort(seen, DateTime)
    assert Enum.uniq(seen) == seen
  end

  test "an agent whose person has not signed in here yet is told person_not_here at every door",
       %{conn: conn} do
    owner = "did:privy:" <> Base.encode16(:crypto.strong_rand_bytes(8), case: :lower)
    wallet = wallet()

    SQL.query!(
      Repo,
      """
      INSERT INTO regent_agents.paired_agents
        (privy_user_id, wallet, name, harness, paired_at, last_contact_at)
      VALUES ($1, $2, 'Probe', 'hermes', now(), now())
      """,
      [owner, wallet]
    )

    NetworkFixture.sign_as(%{wallet_address: wallet})

    for door <- @doors do
      assert error_code(send_to(conn, door), 403) == "person_not_here"
    end
  end

  test "an agent acting as its person passes every door and reads only that person's account",
       %{conn: conn} do
    paired = NetworkFixture.paired_agent()
    NetworkFixture.sign_as(paired)

    assert error_code(send_to(conn, {:post, "/api/v1/publications", "{}"}), 400) != nil

    reports = send_to(conn, {:get, "/api/model-climb/v1/reports", nil})
    assert json_response(reports, 200)["reports"] == []

    balances = json_response(send_to(conn, {:get, "/tools/account/balances", nil}), 200)
    assert balances["account_id"] == paired.human_account_id
    assert balances["pairing_id"] == paired.pairing_id

    assert send_to(conn, {:get, "/tools/account/points", nil}).status == 200
    assert send_to(conn, {:post, "/tools/account/credits/history", "{}"}).status == 200
  end

  describe "an unpairing while the request runs" do
    setup do
      paired = NetworkFixture.paired_agent()
      NetworkFixture.sign_as(paired)

      conn =
        build_conn(:get, "/tools/account/balances")
        |> NetworkFixture.signed()
        |> AgentWallet.call([])

      assert %Techtree.Actors.Agent{pairing: :active} = conn.assigns.actor
      {:ok, paired: paired, conn: conn}
    end

    test "replaces the answer, so the person's data is never sent", %{paired: paired, conn: conn} do
      person = %RegentAgents.Person{privy_user_id: paired.privy_user_id}
      {:ok, pairing} = RegentAgents.get_my_agent(paired.pairing_id, actor: person)
      :ok = RegentAgents.unpair_agent(pairing, actor: person)

      sent = send_resp(conn, 200, ~s({"credits":"the person's balance"}))

      assert sent.status == 403

      assert %{"error" => %{"code" => "agent_not_paired"}} = body = Jason.decode!(sent.resp_body)
      assert Map.keys(body) == ["error"]
    end

    test "leaves the answer alone while the pairing holds", %{conn: conn} do
      sent = send_resp(conn, 200, ~s({"credits":"the person's balance"}))

      assert sent.status == 200
      assert Jason.decode!(sent.resp_body) == %{"credits" => "the person's balance"}
    end
  end

  defp send_to(conn, {method, path, body}, options \\ []) do
    conn = if Keyword.get(options, :signed?, true), do: NetworkFixture.signed(conn), else: conn

    case body do
      nil ->
        dispatch(conn, @endpoint, method, path)

      body ->
        conn
        |> put_req_header("content-type", "application/json")
        |> dispatch(@endpoint, method, path, body)
    end
  end

  defp error_code(conn, status), do: json_response(conn, status)["error"]["code"]

  defp agents(wallet), do: Agent |> Ash.Query.filter(wallet_address == ^wallet) |> Ash.read!()

  defp wallet, do: "0x" <> Base.encode16(:crypto.strong_rand_bytes(20), case: :lower)
end
