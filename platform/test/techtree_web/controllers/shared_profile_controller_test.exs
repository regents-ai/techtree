defmodule TechtreeWeb.SharedProfileControllerTest do
  use TechtreeWeb.ConnCase, async: false

  setup_all do
    database = Techtree.Repo.config()[:database]

    unless database == "techtree_test" <> System.fetch_env!("MIX_TEST_PARTITION"),
      do: raise("Profile tests require the prepared disposable database")

    RegentIdentity.Migrator.up(Techtree.Repo)
    assert RegentIdentity.Migrator.up(Techtree.Repo) == []
    :ok
  end

  setup do
    key = JOSE.JWK.generate_key({:ec, "P-256"})
    {_, public} = key |> JOSE.JWK.to_public() |> JOSE.JWK.to_pem()
    previous = Application.get_env(:techtree, :privy)
    Application.put_env(:techtree, :privy, app_id: "profile-fixture", verification_key: public)
    on_exit(fn -> Application.put_env(:techtree, :privy, previous || []) end)
    %{key: key}
  end

  test "profile page and private API use shared components and signed ownership", %{key: key} do
    html = build_conn() |> get("/profile") |> html_response(200)
    assert html =~ "data-regent-profile"
    assert html =~ "Connect X"
    alias_html = build_conn() |> get("/profile/") |> html_response(200)
    assert alias_html =~ ~s(name="privy-app-id" content="profile-fixture")
    assert build_conn() |> get("/api/v1/profile") |> response(401)

    assert build_conn()
           |> init_test_session(%{profile_id: "forged"})
           |> get("/api/v1/profile")
           |> response(401)

    pair = pair(key, "alice")
    assert api(:get, "/api/v1/profile", pair).status == 404
    created = api(:post, "/api/v1/profile/sync", pair)
    assert created.status == 200
    profile = json_response(created, 200)["profile"]
    assert profile["x"]["verified"]
    assert profile["x"]["username"] == "alice"
    refute Map.has_key?(profile, "privy_user_id")
    assert api(:get, "/api/v1/profile", pair(key, "bob")).status == 404
    updated = api(:patch, "/api/v1/profile", pair, %{display_name: "Shared name"})
    assert json_response(updated, 200)["profile"]["profile_id"] == profile["profile_id"]
    assert json_response(updated, 200)["profile"]["display_name"] == "Shared name"
  end

  test "Privy permissions and metadata stay on the profile document" do
    for path <- ["/profile", "/profile/"] do
      conn = build_conn() |> get(path)
      html = html_response(conn, 200)
      assert html =~ ~s(name="privy-app-id")
      assert html =~ ~s(name="privy-bridge-src")
      assert [policy] = get_resp_header(conn, "content-security-policy")
      assert policy =~ "https://auth.privy.io"
      refute policy =~ "unsafe-eval"
    end

    for path <- ["/", "/docs", "/results"] do
      conn = build_conn() |> get(path)
      html = html_response(conn, 200)
      refute html =~ ~s(name="privy-app-id")
      refute html =~ ~s(name="privy-bridge-src")
      assert [policy] = get_resp_header(conn, "content-security-policy")
      refute policy =~ "auth.privy.io"
      refute policy =~ "unsafe-eval"
    end
  end

  defp api(method, path, pair, body \\ nil) do
    build_conn()
    |> put_req_header("authorization", "Bearer #{pair.access}")
    |> put_req_header("privy-id-token", pair.identity)
    |> put_req_header("content-type", "application/json")
    |> dispatch(@endpoint, method, path, if(body, do: Jason.encode!(body), else: nil))
  end

  defp pair(key, subject) do
    now = System.system_time(:second)

    claims = %{
      "iss" => "privy.io",
      "aud" => "profile-fixture",
      "sub" => subject,
      "iat" => now - 1,
      "exp" => now + 600
    }

    sign = fn claims ->
      {_, token} = key |> JOSE.JWT.sign(%{"alg" => "ES256"}, claims) |> JOSE.JWS.compact()
      token
    end

    accounts = [
      %{
        type: "wallet",
        chain_type: "ethereum",
        address: "0x1111111111111111111111111111111111111111"
      },
      %{type: "twitter_oauth", subject: "x-#{subject}", username: subject}
    ]

    %{
      access: sign.(Map.put(claims, "sid", "fixture-session")),
      identity: sign.(Map.put(claims, "linked_accounts", Jason.encode!(accounts)))
    }
  end
end
