defmodule TechtreeWeb.Plugs.AgentWalletTest do
  use TechtreeWeb.ConnCase, async: false

  alias Ecto.Adapters.SQL
  alias Techtree.NetworkFixture
  alias Techtree.Repo

  test "an agent whose person has not signed in here yet is told person_not_here", %{conn: conn} do
    owner = "did:privy:" <> Base.encode16(:crypto.strong_rand_bytes(8), case: :lower)
    wallet = "0x" <> Base.encode16(:crypto.strong_rand_bytes(20), case: :lower)

    SQL.query!(
      Repo,
      """
      INSERT INTO regent_agents.paired_agents
        (privy_user_id, wallet, name, harness, paired_at, last_contact_at)
      VALUES ($1, $2, 'Probe', 'Hermes Agent', now(), now())
      """,
      [owner, wallet]
    )

    NetworkFixture.sign_as(%{wallet_address: wallet})

    response = conn |> NetworkFixture.signed() |> get(~p"/api/model-climb/v1/reports")

    assert json_response(response, 403)["error"]["code"] == "person_not_here"
  end
end
