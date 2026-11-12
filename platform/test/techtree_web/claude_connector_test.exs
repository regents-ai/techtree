defmodule TechtreeWeb.ClaudeConnectorTest do
  # The Claude connector through this site's own endpoint, router, sign-in and
  # agent records: off, nothing about agents changes; on, each app an account
  # connects pairs its own hosted agent, checks in, and loses access when it
  # disconnects. With the agent permission, a paired app calls as its own paired
  # agent and never as another app's or another account's: which one it is shows
  # as the actor McpAgent set on the answered request.
  # The hosted signer and the SIWA service are stubbed; the rest is the site's.
  use ExUnit.Case, async: false

  import Phoenix.ConnTest, only: [assert_error_sent: 2]
  import Plug.Conn
  import Plug.Test

  alias Techtree.Accounts.{SessionAuthority, VerifiedSession}
  alias Techtree.Actors.{Agent, ConnectedApp}
  alias TechtreeWeb.PairingBox

  @endpoint TechtreeWeb.Endpoint
  @wallet "0x2222222222222222222222222222222222222222"
  @site_key String.duplicate("k", 32)
  @signed %{
    "x-siwa-signature" => "sig1=:c2lnbmVk:",
    "x-siwa-signature-input" =>
      ~s|sig1=("@method" "@path");created=1;expires=2;nonce="n";keyid="k"|,
    "x-siwa-receipt" => "receipt",
    "x-key-id" => "k",
    "x-timestamp" => "1",
    "x-agent-chain-id" => "8453"
  }
  # Every request the hosted signer may be asked to sign for this site.
  @agent_scopes "regent.identity.manage " <> Techtree.OAuth.agent_scope()
  @signable [
    {"GET", "/api/agents/v1/whoami"},
    {"GET", "/api/agents/v1/me"},
    {"POST", "/api/agents/v1/pair"}
  ]

  setup do
    owner = Ecto.Adapters.SQL.Sandbox.start_owner!(Techtree.Repo, shared: true)
    on_exit(fn -> Ecto.Adapters.SQL.Sandbox.stop_owner(owner) end)
    put_env(:regent_agents, :req_options, plug: {Req.Test, RegentAgents.Broker})
    test = self()

    # The SIWA service verifies every signed request as the wallet that signed it.
    Req.Test.stub(RegentAgents.Broker, fn conn ->
      {:ok, body, conn} = read_body(conn)
      payload = Jason.decode!(body)
      send(test, {:verify, conn.req_headers, body, payload})

      Req.Test.json(conn, %{
        "code" => "http_envelope_valid",
        "data" => %{
          "verified" => true,
          "principal" => %{
            "kind" => "wallet",
            "wallet_address" => payload["headers"]["x-agent-wallet-address"],
            "chain_id" => 8453,
            "audience" => "techtree"
          },
          "agentRegistration" => nil,
          "agentBook" => nil
        }
      })
    end)

    :ok
  end

  describe "with the connector off, as config/test.exs and production leave it" do
    test "its sign-in is not found, /mcp takes no app's token, and Claude is neither offered nor accepted" do
      for token <- ["any-token", nil] do
        refused = post_mcp(rpc("ping"), token)
        assert refused.status == 401
        assert get_resp_header(refused, "www-authenticate") == []
      end

      assert @endpoint.call(conn(:get, "/.well-known/oauth-authorization-server"), []).status ==
               404

      assert @endpoint.call(conn(:post, "/oauth/register", %{}), []).status == 404

      refute :claude in RegentAgents.Harness.offered()
      refute "claude" in Enum.map(PairingBox.choices(), & &1.value)
    end

    test "Claude's guide is not found, and no page for agents names it or the MCP address" do
      for path <- ["/agents/claude", "/agents/claude/skill.md"] do
        assert_error_sent(404, fn -> page(path) end)
      end

      for path <- ["/agents", "/llms.txt", "/sitemap.xml"] do
        refute page(path).resp_body =~ claude_guide(), path
      end

      refute page("/llms.txt").resp_body =~ "/mcp"
    end

    test "an agent's sign-in and pairing work as before, and a Claude pairing is refused" do
      subject = "did:privy:connector-off"
      sign_in!(subject)

      whoami = signed(:get, "/api/agents/v1/whoami")
      assert whoami.status == 200
      assert Jason.decode!(whoami.resp_body)["data"]["status"] == "not_paired"

      refused = pair_request(code!(subject), "claude")
      assert refused.status in 400..499
      assert agents(subject) == []

      paired = pair_request(code!(subject), "codex")
      assert paired.status in 200..201, paired.resp_body
      assert [%{harness: :codex, wallet: @wallet}] = agents(subject)
    end
  end

  describe "with the connector on" do
    setup :connector_on

    test "pair_identity makes one paired agent of the authorizing account, from that account's own code only" do
      subject = "did:privy:connector-pair"
      sign_in!(subject)
      %{client_id: client, access: token} = connect!(subject)
      wallet = wallet(subject, client)

      # Another account's code is refused before anything is signed.
      sign_in!("did:privy:connector-other")
      other = code!("did:privy:connector-other")
      assert %{"isError" => true} = tool(token, "pair_identity", pair_args(other))
      assert signer_asks() == []
      assert agents(subject) == [] and agents("did:privy:connector-other") == []

      arguments = pair_args(code!(subject))
      assert %{"isError" => false} = tool(token, "pair_identity", arguments)

      # The POST the hosted signer signed is verified with its exact body.
      assert [%{"operation" => "sign", "request" => signed}] =
               for({_, _, %{"operation" => "sign"} = ask} <- signer_asks(), do: ask)

      assert {signed["method"], signed["path"]} == {"POST", "/api/agents/v1/pair"}
      assert Jason.decode!(signed["body"]) == arguments
      assert_received {:verify, _headers, _raw, payload}
      assert payload["body_digest"] == Siwa.content_digest_for_body(signed["body"])

      assert [%{harness: :claude, wallet: ^wallet, name: "Claude"}] = agents(subject)
    end

    test "Claude is offered in the pairing box, and its guide and the MCP address are named" do
      assert :claude in RegentAgents.Harness.offered()
      assert "claude" in Enum.map(PairingBox.choices(), & &1.value)

      guide = page("/agents/claude")
      assert guide.status == 200
      assert guide.resp_body =~ "Pair New Agent"

      skill = page("/agents/claude/skill.md")
      assert skill.status == 200
      assert skill.resp_body =~ "## On Claude"
      assert skill.resp_body =~ TechtreeWeb.PublicDocuments.url("/mcp")

      for path <- ["/agents", "/llms.txt", "/sitemap.xml"] do
        assert page(path).resp_body =~ claude_guide(), path
      end

      assert page("/llms.txt").resp_body =~ TechtreeWeb.PublicDocuments.url("/mcp")
    end

    test "a first request with no token is asked to connect, so the app starts its sign-in" do
      for body <- [rpc("initialize", %{"protocolVersion" => "2025-06-18"}), rpc("tools/list")] do
        refused = post_mcp(body, nil)
        assert refused.status == 401
        assert json(refused)["error"]["code"] == "connection_required"

        assert get_resp_header(refused, "www-authenticate") ==
                 [RegentOAuth.challenge(Enum.join(RegentOAuth.scopes(), " "))]
      end
    end

    test "pair_identity takes what the library takes, and input it cannot take gets the library's pairing refusal" do
      subject = "did:privy:connector-input"
      sign_in!(subject)
      %{access: token} = connect!(subject)

      listed = json(post_mcp(rpc("tools/list"), token))["result"]["tools"]

      schema =
        Enum.find(listed, &(&1["name"] == "pair_identity"))["inputSchema"]["properties"]["input"]

      assert schema["properties"]["harness"]["enum"] == RegentMCPAgents.hosted_names()
      assert Enum.sort(schema["required"]) == ["code", "harness", "name"]

      for args <- [
            %{pair_args("A-CODE") | "name" => String.duplicate("n", 101)},
            %{pair_args("A-CODE") | "code" => String.duplicate("c", 129)},
            %{pair_args("A-CODE") | "harness" => "codex"},
            Map.delete(pair_args("A-CODE"), "name")
          ] do
        assert %{"isError" => true, "content" => [%{"text" => text}]} =
                 tool(token, "pair_identity", args)

        refute text =~ "%{"
        assert Jason.decode!(text)["error"]["code"] == "invalid_request"
      end

      assert agents(subject) == []
    end

    test "a signer that asks for a wait gives pair_identity the seconds to wait" do
      subject = "did:privy:connector-wait"
      sign_in!(subject)
      %{access: token} = connect!(subject)

      Req.Test.stub(RegentMCPAgents.HostedSigner, fn conn ->
        {:ok, body, conn} = read_body(conn)

        case Jason.decode!(body) do
          %{"operation" => "register"} ->
            Req.Test.json(conn, %{"address" => @wallet})

          %{"operation" => "sign"} ->
            conn
            |> put_resp_header("retry-after", "45")
            |> put_status(429)
            |> Req.Test.json(%{})
        end
      end)

      assert %{"isError" => true, "content" => [%{"text" => text}]} =
               tool(token, "pair_identity", pair_args(code!(subject)))

      assert %{"code" => "too_many_requests", "retry_after" => 45} = Jason.decode!(text)["error"]
      assert agents(subject) == []
    end

    test "a connected app lists and runs only its identity tools, never Techtree's agent work" do
      subject = "did:privy:connector-scope"
      sign_in!(subject)
      %{access: token} = connect!(subject)

      listed = json(post_mcp(rpc("tools/list"), token))["result"]["tools"]
      assert Enum.sort(Enum.map(listed, & &1["name"])) == Enum.sort(RegentMCPAgents.Tools.names())

      for name <- ["techtree_start", "techtree_publication", "account_points"] do
        call = rpc("tools/call", %{"name" => name, "arguments" => %{"input" => %{}}})
        assert %{"error" => _} = json(post_mcp(call, token))
      end

      assert signer_asks() == []
    end

    test "the hosted signer signs only the identity requests, as this app's one identity, and the connection's token stays here" do
      subject = "did:privy:connector-allowlist"
      sign_in!(subject)
      %{client_id: client, access: token} = connect!(subject)

      assert %{"isError" => false} = tool(token, "register_identity")
      assert %{"isError" => false} = tool(token, "get_identity")
      assert %{"isError" => false} = tool(token, "pair_identity", pair_args(code!(subject)))

      # A call may also leave arguments out.
      assert %{"isError" => false} =
               json(post_mcp(rpc("tools/call", %{"name" => "check_in"}), token))["result"]

      assert %{"error" => _} = json(post_mcp(rpc("tools/call", %{"name" => "post"}), token))

      key = key(subject, client)
      asked = signer_asks()

      for {auth, raw, ask} <- asked do
        assert auth == ["Bearer " <> @site_key]
        assert ask["identity_key"] == key
        refute raw =~ token
      end

      signed = for {_, _, %{"operation" => "sign", "request" => r}} <- asked, do: r
      assert length(signed) == 3
      assert Enum.map(signed, &{&1["method"], &1["path"]}) -- @signable == []

      for _ <- signed do
        assert_received {:verify, headers, raw, _payload}
        refute raw =~ token
        refute Enum.any?(headers, fn {_name, value} -> value =~ token end)
      end
    end

    test "a refreshed token keeps its app's identity and agent; another app of the account starts unpaired" do
      subject = "did:privy:connector-again"
      sign_in!(subject)
      first = connect!(subject)

      assert %{"isError" => false} =
               tool(first.access, "pair_identity", pair_args(code!(subject)))

      [%{id: agent_id}] = agents(subject)

      assert {200, %{"access_token" => refreshed}} = refresh(first.client_id, first.refresh)

      assert %{"structuredContent" => %{"paired" => true, "identity_id" => id}} =
               tool(refreshed, "get_identity")

      assert id == key(subject, first.client_id)
      assert %{"isError" => false} = tool(refreshed, "check_in")

      # A second app the same person connects has its own identity, unpaired.
      second = connect!(subject)

      assert %{"structuredContent" => %{"paired" => false, "identity_id" => second_id}} =
               tool(second.access, "get_identity")

      assert second_id == key(subject, second.client_id)
      refute second_id == id
      assert %{"isError" => true} = tool(second.access, "check_in")
      assert [%{id: ^agent_id}] = agents(subject)

      # With a code of its own it pairs as a second agent, with its own wallet.
      assert %{"isError" => false} =
               tool(second.access, "pair_identity", pair_args(code!(subject)))

      assert agents(subject) |> Enum.map(& &1.wallet) |> Enum.sort() ==
               Enum.sort([wallet(subject, first.client_id), wallet(subject, second.client_id)])
    end

    test "only a check-in moves when the agent was last in touch" do
      subject = "did:privy:connector-touch"
      sign_in!(subject)
      %{client_id: client, access: token, refresh: refresh_token} = connect!(subject)
      assert %{"isError" => false} = tool(token, "pair_identity", pair_args(code!(subject)))
      [%{last_contact_at: paired_at}] = agents(subject)

      assert post_mcp(rpc("initialize", %{"protocolVersion" => "2025-06-18"}), token).status ==
               200

      assert post_mcp(rpc("ping"), token).status == 200
      assert {200, %{"access_token" => refreshed}} = refresh(client, refresh_token)
      assert %{"isError" => false} = tool(refreshed, "get_identity")
      assert %{"isError" => false} = tool(refreshed, "register_identity")
      assert [%{last_contact_at: ^paired_at}] = agents(subject)

      assert %{"isError" => false} = tool(refreshed, "check_in")
      assert [%{last_contact_at: checked_in}] = agents(subject)
      assert DateTime.after?(checked_in, paired_at)
    end

    test "unpairing on the Agents page holds: a check-in is refused and pairs nothing again" do
      subject = "did:privy:connector-unpair"
      sign_in!(subject)
      %{access: token} = connect!(subject)
      assert %{"isError" => false} = tool(token, "pair_identity", pair_args(code!(subject)))
      [agent] = agents(subject)

      :ok = RegentAgents.unpair_agent!(agent, actor: person(subject))

      assert %{"isError" => true} = tool(token, "check_in")
      assert %{"structuredContent" => %{"paired" => false}} = tool(token, "get_identity")
      assert agents(subject) == []
    end

    test "disconnecting at Connected apps revokes the app's tokens: its next call is asked to sign in" do
      subject = "did:privy:connector-revoke"
      browser = sign_in!(subject)
      %{client_id: client, access: token, refresh: refresh_token} = connect!(subject)
      assert %{"isError" => false} = tool(token, "register_identity")

      csrf = Plug.CSRFProtection.get_csrf_token()

      revoked =
        conn(:post, "/oauth/connections/revoke", %{"client_id" => client, "_csrf_token" => csrf})
        |> init_test_session(Map.put(browser, "_csrf_token", Plug.CSRFProtection.dump_state()))
        |> put_req_header("accept", "text/html")
        |> @endpoint.call([])

      assert revoked.status == 303
      assert get_resp_header(revoked, "location") == ["/oauth/connections"]

      refused = post_mcp(rpc("tools/call", %{"name" => "check_in", "arguments" => %{}}), token)
      assert refused.status == 401
      assert [_challenge] = get_resp_header(refused, "www-authenticate")
      assert {400, %{"error" => "invalid_grant"}} = refresh(client, refresh_token)
    end
  end

  describe "with the connector on and the agent permission" do
    setup :connector_on

    test "a paired account's app calls as its agent, and its identity tools still answer" do
      subject = "did:privy:agent-paired"
      sign_in!(subject)
      %{access: token} = connect!(subject, @agent_scopes)
      assert %{"isError" => false} = tool(token, "pair_identity", pair_args(code!(subject)))
      [%{wallet: wallet}] = agents(subject)

      assert %Agent{pairing: :active, privy_user_id: ^subject, wallet_address: ^wallet} =
               agent = actor(post_mcp(rpc("tools/list"), token))

      assert agent.connection.subject == subject

      # As the agent it also has the agent's tool, a message for the team.
      assert Enum.sort(tool_names(token)) ==
               Enum.sort(["messages_leave" | RegentMCPAgents.Tools.names()])

      assert %{"isError" => false} = tool(token, "check_in")
    end

    test "a token without the agent permission stays the app, paired or not" do
      subject = "did:privy:agent-identity-only"
      sign_in!(subject)
      %{access: token} = connect!(subject)
      assert %{"isError" => false} = tool(token, "pair_identity", pair_args(code!(subject)))
      assert %ConnectedApp{} = actor(post_mcp(rpc("tools/list"), token))
    end

    test "a second app of an account already paired through another app has its identity tools only" do
      subject = "did:privy:agent-look-alike"
      sign_in!(subject)
      %{access: first} = connect!(subject, @agent_scopes)
      assert %{"isError" => false} = tool(first, "pair_identity", pair_args(code!(subject)))
      assert %Agent{pairing: :active} = actor(post_mcp(rpc("tools/list"), first))

      # Same account, same name, the agent permission: still not the paired agent.
      %{access: token} = connect!(subject, @agent_scopes)
      assert %ConnectedApp{} = actor(post_mcp(rpc("tools/list"), token))
      assert Enum.sort(tool_names(token)) == Enum.sort(RegentMCPAgents.Tools.names())
      assert %{"structuredContent" => %{"paired" => false}} = tool(token, "get_identity")
      assert %{"isError" => true} = tool(token, "check_in")
      assert [_only] = agents(subject)
    end

    test "another account's token never acts as the first account's paired agent" do
      paired = "did:privy:agent-first"
      other = "did:privy:agent-other"
      sign_in!(paired)
      sign_in!(other)
      %{access: first} = connect!(paired, @agent_scopes)
      assert %{"isError" => false} = tool(first, "pair_identity", pair_args(code!(paired)))

      # Even a hosted signer that answered every account with the first one's
      # paired wallet would not make the other account its agent.
      [%{wallet: wallet}] = agents(paired)

      Req.Test.stub(RegentMCPAgents.HostedSigner, fn conn ->
        Req.Test.json(conn, %{"address" => wallet})
      end)

      %{access: token} = connect!(other, @agent_scopes)
      assert %ConnectedApp{principal: %{subject: ^other}} = actor(post_mcp(rpc("ping"), token))
    end

    test "unpairing makes the app itself again on the next call" do
      subject = "did:privy:agent-unpair"
      sign_in!(subject)
      %{access: token} = connect!(subject, @agent_scopes)
      assert %{"isError" => false} = tool(token, "pair_identity", pair_args(code!(subject)))
      assert %Agent{pairing: :active} = actor(post_mcp(rpc("ping"), token))

      [agent] = agents(subject)
      :ok = RegentAgents.unpair_agent!(agent, actor: person(subject))
      assert %ConnectedApp{} = actor(post_mcp(rpc("ping"), token))
    end

    test "the hosted signer is asked for the app's address once, not on every call" do
      subject = "did:privy:agent-once"
      sign_in!(subject)
      %{access: token} = connect!(subject, @agent_scopes)
      for _ <- 1..3, do: post_mcp(rpc("ping"), token)
      assert Enum.count(signer_asks(), &match?({_, _, %{"operation" => "register"}}, &1)) <= 1
    end

    test "while the hosted signer is down, each call is refused and asks again; its first answer is kept" do
      subject = "did:privy:agent-down"
      sign_in!(subject)
      %{access: token} = connect!(subject, @agent_scopes)
      test = self()

      Req.Test.stub(RegentMCPAgents.HostedSigner, fn conn ->
        send(test, :signer_asked)
        conn |> put_status(503) |> Req.Test.json(%{})
      end)

      for _ <- 1..3 do
        refused = post_mcp(rpc("ping"), token)
        assert refused.status == 503
        assert json(refused)["error"]["code"] == "identity_unavailable"
      end

      assert signer_asked() == 3

      Req.Test.stub(RegentMCPAgents.HostedSigner, fn conn ->
        send(test, :signer_asked)
        Req.Test.json(conn, %{"address" => @wallet})
      end)

      for _ <- 1..3, do: assert(post_mcp(rpc("ping"), token).status == 200)
      assert signer_asked() == 1
    end

    test "only a check-in moves when the agent was last in touch" do
      subject = "did:privy:agent-touch"
      sign_in!(subject)
      %{access: token} = connect!(subject, @agent_scopes)
      assert %{"isError" => false} = tool(token, "pair_identity", pair_args(code!(subject)))
      [%{last_contact_at: paired_at}] = agents(subject)

      Process.sleep(1100)
      assert post_mcp(rpc("ping"), token).status == 200
      assert %Agent{pairing: :active} = actor(post_mcp(rpc("tools/list"), token))
      assert [%{last_contact_at: ^paired_at}] = agents(subject)
    end
  end

  describe "the hosted MCP server's address budgets, with the connector on" do
    setup :connector_on

    test "a token that isn't this site's spends its address's 120, and one past them is refused before any token is looked up" do
      from = {10, 9, 8, 7}
      first = post_mcp(rpc("ping"), "not-this-sites", from)
      assert first.status == 401
      assert policies(first) == ["mcp_address"]
      assert oauth_calls(fn -> post_mcp(rpc("ping"), "not-this-sites", from) end) > 0

      for _ <- 3..120, do: assert(post_mcp(rpc("ping"), "not-this-sites", from).status == 401)

      assert oauth_calls(fn ->
               refused = post_mcp(rpc("ping"), "not-this-sites", from)
               assert refused.status == 429
               assert policies(refused) == ["mcp_address"]
             end) == 0
    end

    test "a checked token spends its address's 600 and its account's 120, never the address's 120" do
      subject = "did:privy:budget-checked"
      sign_in!(subject)
      %{access: token} = connect!(subject)
      answered = post_mcp(rpc("ping"), token, {10, 9, 8, 6})
      assert answered.status == 200
      assert policies(answered) == ["mcp_connected_address", "mcp"]
    end

    test "every answer is private and never kept, a tool's, a stream's and a refusal" do
      subject = "did:privy:budget-private"
      sign_in!(subject)
      %{access: token} = connect!(subject)

      # AshAi streams this answer and names its own cache-control on it.
      version = "2026-07-28"

      meta = %{
        "io.modelcontextprotocol/protocolVersion" => version,
        "io.modelcontextprotocol/clientCapabilities" => %{}
      }

      listen = rpc("subscriptions/listen", %{"_meta" => meta})

      stream =
        post_mcp(listen, token, {127, 0, 0, 1}, [
          {"mcp-protocol-version", version},
          {"mcp-method", "subscriptions/listen"}
        ])

      assert get_resp_header(stream, "content-type") == ["text/event-stream"]

      for answer <- [
            stream,
            post_mcp(rpc("tools/list"), token),
            post_mcp(rpc("ping"), nil),
            post_mcp(rpc("ping"), "not-this-sites")
          ] do
        assert get_resp_header(answer, "cache-control") == ["private, no-store"]
      end
    end
  end

  # Switches the connector on for one test as config/runtime.exs does with
  # TECHTREE_CLAUDE_CONNECTOR_ENABLED=true, and starts its sign-in store in
  # this test's transaction; everything is put back after.
  defp connector_on(_context) do
    origin = "http://127.0.0.1:4002"

    put_env(
      :techtree,
      Techtree.OAuth,
      Keyword.merge(Application.fetch_env!(:techtree, Techtree.OAuth),
        enabled?: true,
        issuer: origin,
        resource: origin <> "/mcp"
      )
    )

    put_env(
      :regent_mcp_agents,
      :config,
      Keyword.merge(Application.fetch_env!(:regent_mcp_agents, :config),
        enabled?: true,
        hosted_signer: [base_url: "https://siwa.test", key: @site_key]
      )
    )

    put_env(:regent_agents, :hosted_pairing, [:claude])
    put_env(:regent_mcp_agents, :req_options, plug: {Req.Test, RegentMCPAgents.HostedSigner})
    for key <- [RegentOAuth.Repo, :site, :prefix], do: keep_env(:regent_oauth, key)
    keep_env(:boruta, Boruta.Oauth)

    :ok = RegentOAuth.configure(Techtree.OAuth)
    :ok = RegentMCPAgents.configure!()

    Application.put_env(
      :regent_oauth,
      RegentOAuth.Repo,
      Keyword.put(
        Application.fetch_env!(:regent_oauth, RegentOAuth.Repo),
        :pool,
        Ecto.Adapters.SQL.Sandbox
      )
    )

    start_supervised!(RegentOAuth.Repo)
    oauth = Ecto.Adapters.SQL.Sandbox.start_owner!(RegentOAuth.Repo, shared: true)
    on_exit(fn -> Ecto.Adapters.SQL.Sandbox.stop_owner(oauth) end)

    test = self()

    # The hosted signer registers each identity and signs what it is asked to, as
    # that identity's own wallet.
    Req.Test.stub(RegentMCPAgents.HostedSigner, fn conn ->
      {:ok, body, conn} = read_body(conn)
      asked = Jason.decode!(body)
      send(test, {:signer, get_req_header(conn, "authorization"), body, asked})
      wallet = identity_wallet(asked["identity_key"])

      case asked do
        %{"operation" => "register"} ->
          Req.Test.json(conn, %{"address" => wallet})

        %{"operation" => "sign", "request" => r} ->
          headers = Map.put(@signed, "x-agent-wallet-address", wallet)
          Req.Test.json(conn, Map.put(r, "headers", headers))
      end
    end)

    :ok
  end

  defp put_env(app, key, value) do
    keep_env(app, key)
    Application.put_env(app, key, value)
  end

  defp keep_env(app, key) do
    old = Application.fetch_env(app, key)

    on_exit(fn ->
      case old do
        {:ok, value} -> Application.put_env(app, key, value)
        :error -> Application.delete_env(app, key)
      end
    end)
  end

  # A person signed in on this site; answers the session their browser holds.
  defp sign_in!(subject) do
    {:ok, account, []} =
      VerifiedSession.establish(%RegentPrivy.Session{
        app_id: "test-app",
        session_id: subject,
        privy_user_id: subject,
        wallet_address: "0x3333333333333333333333333333333333333333",
        wallet_addresses: ["0x3333333333333333333333333333333333333333"],
        linked_socials: [],
        issued_at: System.system_time(:second),
        expires_at: System.system_time(:second) + 3600
      })

    {:bootstrap, claim} = SessionAuthority.renew(nil)
    {:ok, :bind, bound} = SessionAuthority.sign_in(claim, account.id)
    SessionAuthority.session(bound)
  end

  # An app connected by `subject`, as consent leaves it: its client id and the
  # plain access and refresh tokens it holds.
  defp connect!(subject, scope \\ "regent.identity.manage") do
    register =
      conn(:post, "/oauth/register", %{
        "client_name" => "Claude",
        "redirect_uris" => ["https://claude.ai/api/mcp/auth_callback"]
      })
      |> put_req_header("accept", "application/json")
      |> @endpoint.call([])

    assert register.status == 201, register.resp_body
    client = Boruta.ClientsAdapter.get_client(json(register)["client_id"])

    {:ok, token} =
      RegentOAuth.AccessTokens.create(
        %{client: client, sub: subject, scope: scope},
        refresh_token: true
      )

    %{client_id: client.id, access: token.value, refresh: token.refresh_token}
  end

  defp refresh(client_id, refresh_token) do
    conn =
      conn(:post, "/oauth/token", %{
        "grant_type" => "refresh_token",
        "client_id" => client_id,
        "refresh_token" => refresh_token,
        "resource" => RegentOAuth.resource()
      })
      |> put_req_header("accept", "application/json")
      |> @endpoint.call([])

    {conn.status, json(conn)}
  end

  # AshAi takes a tool's arguments as its action's input.
  # A call as tools/list lists the tool: one with no inputs is sent empty
  # arguments; one with inputs takes them under `input`.
  defp tool(token, name),
    do: json(post_mcp(rpc("tools/call", %{"name" => name, "arguments" => %{}}), token))["result"]

  defp tool(token, name, input) do
    call = rpc("tools/call", %{"name" => name, "arguments" => %{"input" => input}})
    json(post_mcp(call, token))["result"]
  end

  defp post_mcp(body, token, from \\ {127, 0, 0, 1}, headers \\ []) do
    conn =
      Enum.reduce(
        headers,
        conn(:post, "/mcp", Jason.encode!(body))
        |> Map.put(:remote_ip, from)
        |> put_req_header("content-type", "application/json")
        |> put_req_header("accept", "application/json, text/event-stream"),
        fn {name, value}, conn -> put_req_header(conn, name, value) end
      )

    conn = if token, do: put_req_header(conn, "authorization", "Bearer " <> token), else: conn
    @endpoint.call(conn, [])
  end

  defp rpc(method, params \\ %{}),
    do: %{"jsonrpc" => "2.0", "id" => 1, "method" => method, "params" => params}

  # An agent's signed request, verified by the stubbed SIWA service.
  defp signed(method, path, body \\ nil) do
    conn = conn(method, path, body)
    conn = if body, do: put_req_header(conn, "content-type", "application/json"), else: conn

    conn
    |> put_req_header("x-siwa-signature", "fixture-proof")
    |> put_req_header("x-agent-wallet-address", @wallet)
    |> @endpoint.call([])
  end

  defp pair_request(code, harness),
    do:
      signed(
        :post,
        "/api/agents/v1/pair",
        Jason.encode!(%{code: code, name: "Fixture", harness: harness})
      )

  defp pair_args(code), do: %{"code" => code, "name" => "Claude", "harness" => "claude"}

  defp person(subject), do: %RegentAgents.Person{privy_user_id: subject}

  # Each connected app's identity for an account, and that identity's own wallet.
  defp key(subject, client), do: RegentMCPAgents.identity_key("techtree", subject, client)
  defp wallet(subject, client), do: identity_wallet(key(subject, client))
  defp identity_wallet(key), do: "0x" <> binary_part(key, 0, 40)

  defp code!(subject), do: RegentAgents.issue_pairing_code!(actor: person(subject)).code

  defp agents(subject), do: RegentAgents.list_my_agents!(actor: person(subject))

  defp signer_asks do
    receive do
      {:signer, auth, raw, asked} -> [{auth, raw, asked} | signer_asks()]
    after
      0 -> []
    end
  end

  defp tool_names(token) do
    json(post_mcp(rpc("tools/list"), token))["result"]["tools"]
    |> Enum.map(& &1["name"])
  end

  # Claude's guide's address, never Claude Code's.
  defp claude_guide,
    do: ~r{#{Regex.escape(TechtreeWeb.PublicDocuments.url("/agents/claude"))}(?![\w-])}

  # A public page as a browser asks for it.
  defp page(path) do
    conn(:get, path)
    |> put_req_header("accept", "text/html")
    |> @endpoint.call([])
  end

  # Who McpAgent let the request through as.
  defp actor(conn), do: Ash.PlugHelpers.get_actor(conn)

  defp signer_asked do
    receive do
      :signer_asked -> 1 + signer_asked()
    after
      0 -> 0
    end
  end

  # The budgets an answer was counted under, in order.
  defp policies(conn) do
    [header] = get_resp_header(conn, "ratelimit-policy")
    for [_, policy] <- Regex.scan(~r/"([^"]+)"/, header), do: policy
  end

  # How many calls the sign-in store took while `fun` ran. It sends nothing to
  # telemetry, so this process's calls into it are traced, to a process of their
  # own: a process is never its own tracer.
  defp oauth_calls(fun) do
    test = self()
    tracer = spawn_link(fn -> count_calls(test, 0) end)
    :erlang.trace_pattern({RegentOAuth.Repo, :_, :_}, true, [])
    :erlang.trace(test, true, [:call, {:tracer, tracer}])
    fun.()
    :erlang.trace(test, false, [:call])
    :erlang.trace_pattern({RegentOAuth.Repo, :_, :_}, false, [])
    delivered = :erlang.trace_delivered(test)
    assert_receive {:trace_delivered, ^test, ^delivered}
    send(tracer, :done)
    assert_receive {:calls, calls}
    calls
  end

  defp count_calls(test, calls) do
    receive do
      {:trace, ^test, :call, {RegentOAuth.Repo, _name, _args}} -> count_calls(test, calls + 1)
      :done -> send(test, {:calls, calls})
    end
  end

  defp json(conn), do: Jason.decode!(conn.resp_body)
end
