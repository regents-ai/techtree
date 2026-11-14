defmodule TechtreeWeb.ProfileTest do
  @moduledoc """
  The person's shared profile at `/api/v1/profile`, reached the two ways it
  answers: the person signed in on this site, through the site's own sign-in
  addresses, and an agent the person paired. Only the outside services' verdicts
  are stand-ins: Privy's tokens are signed with a key this test sets, and an
  agent's signature is answered by `NetworkFixture.sign_as/1`.
  """

  use TechtreeWeb.ConnCase, async: false

  alias Techtree.NetworkFixture

  setup do
    key = JOSE.JWK.generate_key({:ec, "P-256"})
    {_, public} = key |> JOSE.JWK.to_public() |> JOSE.JWK.to_pem()
    previous = Application.fetch_env!(:techtree, :privy)
    Application.put_env(:techtree, :privy, Keyword.put(previous, :verification_key, public))
    on_exit(fn -> Application.put_env(:techtree, :privy, previous) end)
    %{key: key}
  end

  test "signing in gives the person their profile", %{key: key} do
    did = did()
    assert {:ok, nil} = RegentIdentity.profile_id(app_id(), did)

    person = sign_in!(key, did)

    assert {:ok, id} = RegentIdentity.profile_id(app_id(), did)
    assert %{"profile_id" => ^id, "display_name" => nil} = profile(read(person), 200)
  end

  test "the person signed in here reads their profile and saves their name", %{key: key} do
    person = sign_in!(key, did())

    assert profile(change(person, %{display_name: "Ada Lovelace"}), 200)["display_name"] ==
             "Ada Lovelace"

    assert profile(read(person), 200)["display_name"] == "Ada Lovelace"
  end

  test "a change without the session's own forms token is refused and changes nothing", %{
    key: key
  } do
    person = sign_in!(key, did())
    other = sign_in!(key, did())

    for token <- [nil, other.token] do
      refused = change(person, %{display_name: "Forged"}, %{"x-csrf-token" => token})
      assert error_code(refused, 401) == "authentication_required"
    end

    # The person is still signed in, and their name is as it was.
    assert profile(read(person), 200)["display_name"] == nil
  end

  test "signed out, the profile is neither read nor changed" do
    browser = build_conn() |> Map.put(:remote_ip, address()) |> get("/auth/csrf")
    visitor = %{conn: browser, token: json_response(browser, 200)["csrf_token"]}

    for refused <- [
          get(build_conn(), "/api/v1/profile"),
          build_conn()
          |> put_req_header("content-type", "application/json")
          |> patch("/api/v1/profile", ~s({"display_name":"Nobody"})),
          read(visitor),
          change(visitor, %{display_name: "Nobody"})
        ] do
      assert error_code(refused, 401) == "authentication_required"
    end
  end

  test "one person neither reads nor changes another's profile", %{key: key} do
    ada = sign_in!(key, did())
    bob = sign_in!(key, did())

    adas = profile(change(ada, %{display_name: "Ada"}), 200)
    bobs = profile(read(bob), 200)
    refute bobs["profile_id"] == adas["profile_id"]
    assert bobs["display_name"] == nil

    refused =
      change(bob, %{display_name: "Not Ada"}, %{"x-regent-profile-id" => adas["profile_id"]})

    assert error_code(refused, 422) == "invalid_profile_update"
    assert profile(read(ada), 200)["display_name"] == "Ada"
    assert profile(read(bob), 200)["display_name"] == nil
  end

  test "a paired agent reads and names its own person's profile, and no one else's", %{key: key} do
    did = did()
    person = sign_in!(key, did)
    other = sign_in!(key, did())
    NetworkFixture.sign_as(NetworkFixture.paired_agent(did, wallet()))

    agent = build_conn() |> NetworkFixture.signed()
    assert profile(get(agent, "/api/v1/profile"), 200) == profile(read(person), 200)

    named =
      agent
      |> put_req_header("content-type", "application/json")
      |> patch("/api/v1/profile", ~s({"display_name":"Named by my agent"}))

    assert profile(named, 200)["display_name"] == "Named by my agent"
    assert profile(read(person), 200)["display_name"] == "Named by my agent"
    assert profile(read(other), 200)["display_name"] == nil
  end

  test "withdrawn profile documents grant no Privy permissions" do
    for path <- ["/profile", "/profile/"] do
      conn = build_conn() |> get(path)
      assert html_response(conn, 404)
      policy = Enum.join(get_resp_header(conn, "content-security-policy"), "; ")
      refute policy =~ "https://auth.privy.io"
      refute policy =~ "unsafe-eval"
    end

    for path <- ["/", "/docs", "/results"] do
      conn = build_conn() |> get(path)
      assert html_response(conn, 200)
      assert [policy] = get_resp_header(conn, "content-security-policy")
      refute policy =~ "unsafe-eval"
    end
  end

  # The browser's own sign-in: a forms token from /auth/csrf, Privy's two tokens
  # to /auth/privy/session, then the forms token the signed-in session's pages
  # hold. Each sign-in comes from its own address, inside the sign-in budget.
  defp sign_in!(key, did) do
    browser = build_conn() |> Map.put(:remote_ip, address()) |> get("/auth/csrf")
    %{access: access, identity: identity} = privy_tokens(key, did)

    signed_in =
      browser
      |> recycle([])
      |> put_req_header("authorization", "Bearer " <> access)
      |> put_req_header("privy-id-token", identity)
      |> put_req_header("x-csrf-token", json_response(browser, 200)["csrf_token"])
      |> post("/auth/privy/session")

    assert json_response(signed_in, 200)["authenticated"]

    page = signed_in |> recycle([]) |> get("/auth/csrf")
    %{conn: page, token: json_response(page, 200)["csrf_token"]}
  end

  defp read(%{conn: conn}), do: conn |> recycle([]) |> get("/api/v1/profile")

  # A change as the session's own pages send it, with its forms token unless
  # `headers` says otherwise; the forms token is checked as it is for a browser.
  defp change(%{conn: conn, token: token}, body, headers \\ %{}) do
    conn =
      conn
      |> recycle([])
      |> put_private(:plug_skip_csrf_protection, false)
      |> put_req_header("content-type", "application/json")

    %{"x-csrf-token" => token}
    |> Map.merge(headers)
    |> Enum.reduce(conn, fn
      {_name, nil}, conn -> conn
      {name, value}, conn -> put_req_header(conn, name, value)
    end)
    |> patch("/api/v1/profile", Jason.encode!(body))
  end

  defp profile(conn, status), do: json_response(conn, status)["profile"]

  defp error_code(conn, status), do: json_response(conn, status)["error"]["code"]

  defp privy_tokens(key, did) do
    now = System.system_time(:second)

    claims = %{
      "iss" => "privy.io",
      "aud" => app_id(),
      "sub" => did,
      "iat" => now - 1,
      "exp" => now + 600
    }

    wallet = %{type: "wallet", chain_type: "ethereum", address: wallet(), lv: now - 1}

    sign = fn claims ->
      {_, token} = key |> JOSE.JWT.sign(%{"alg" => "ES256"}, claims) |> JOSE.JWS.compact()
      token
    end

    %{
      access: sign.(Map.put(claims, "sid", "session-" <> did)),
      identity: sign.(Map.put(claims, "linked_accounts", Jason.encode!([wallet])))
    }
  end

  defp app_id, do: :techtree |> Application.fetch_env!(:privy) |> Keyword.fetch!(:app_id)

  defp did, do: "did:privy:" <> Base.encode16(:crypto.strong_rand_bytes(8), case: :lower)

  defp wallet, do: "0x" <> Base.encode16(:crypto.strong_rand_bytes(20), case: :lower)

  defp address, do: {198, 18, 2, rem(System.unique_integer([:positive]), 254) + 1}
end
