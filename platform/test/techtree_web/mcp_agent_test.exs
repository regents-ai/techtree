defmodule TechtreeWeb.McpAgentTest do
  # The hosted MCP server at /mcp says who is calling as the agent access spec
  # (4.3) sets out, through this site's own endpoint and router:
  # - every request carries an agent's signature or a connected app's token, never
  #   both, and a signature the sign-in service refuses is refused;
  # - an agent's signed call is admitted as that agent, and its one tool here
  #   leaves the team a message (TechtreeWeb.MessagesApiTest);
  # - a query string, a page from another site, a batch, a body that is not JSON
  #   and any other method or address are refused in the site's shape, before
  #   any signature is checked;
  # - one address gets the API's 120 requests a minute.
  # A connected app's own calls are in TechtreeWeb.ClaudeConnectorTest. The
  # sign-in service is stubbed: it vouches for the wallet a request names when the
  # request carries the fixture proof. Each test calls from its own address, so it
  # spends its own rate budgets, not the rest of the suite's.
  use ExUnit.Case, async: false

  import Phoenix.ConnTest, only: [assert_error_sent: 2]
  import Plug.Conn
  import Plug.Test

  alias Techtree.Actors.Agent
  alias Techtree.Repo
  alias TechtreeWeb.PublicDocuments

  @endpoint TechtreeWeb.Endpoint

  setup do
    owner = Ecto.Adapters.SQL.Sandbox.start_owner!(Repo, shared: true)
    on_exit(fn -> Ecto.Adapters.SQL.Sandbox.stop_owner(owner) end)

    Req.Test.stub(RegentAgents.Broker, fn conn ->
      {:ok, body, conn} = read_body(conn)
      headers = Jason.decode!(body)["headers"]

      if headers["x-siwa-signature"] == "fixture-proof" do
        wallet = headers["x-agent-wallet-address"]

        Req.Test.json(conn, %{
          code: "http_envelope_valid",
          data: %{
            verified: true,
            walletAddress: wallet,
            agentBook: nil,
            agentRegistration: nil,
            principal: %{
              kind: "wallet",
              wallet_address: wallet,
              chain_id: 8453,
              audience: "techtree"
            }
          }
        })
      else
        conn
        |> put_status(401)
        |> Req.Test.json(%{
          error: %{
            code: "http_signature_invalid",
            message: "Signature invalid",
            hint: "Sign again"
          }
        })
      end
    end)

    %{from: {10, :rand.uniform(250), :rand.uniform(250), :rand.uniform(250)}}
  end

  test "a signature and a token together are refused, and a token alone while connecting apps is off",
       %{from: from} do
    both = mcp(rpc("tools/list"), from: from, proof: wallet(), token: "a-token")
    assert both.status == 401
    assert error(both)["code"] == "ambiguous_credentials"

    token = mcp(rpc("tools/list"), from: from, token: "a-token")
    assert token.status == 401
    assert error(token)["code"] == "delegated_access_not_enabled"
  end

  test "a signature the sign-in service refuses is refused", %{from: from} do
    refused = mcp(rpc("tools/list"), from: from, proof: wallet(), signature: "forged")
    assert refused.status == 401
    assert error(refused)["code"] == "http_signature_invalid"
  end

  test "an agent's signed call is admitted as that agent, with the one tool that is its own here",
       %{from: from} do
    agent = wallet()
    listed = mcp(rpc("tools/list"), from: from, proof: agent)

    assert listed.status == 200
    assert get_resp_header(listed, "cache-control") == ["private, no-store"]
    assert %Agent{wallet_address: ^agent, connection: nil} = Ash.PlugHelpers.get_actor(listed)
    assert [%{"name" => "messages_leave"}] = result(listed)["tools"]

    call = mcp(call("register_identity", %{}), from: from, proof: agent)
    assert %{"error" => _} = Jason.decode!(call.resp_body)
  end

  test "every request needs a signature or a token, from the first one on", %{from: from} do
    initialize = %{
      "jsonrpc" => "2.0",
      "id" => 1,
      "method" => "initialize",
      "params" => %{
        "protocolVersion" => "2025-06-18",
        "capabilities" => %{},
        "clientInfo" => %{"name" => "t", "version" => "1"}
      }
    }

    for body <- [initialize, rpc("tools/list"), call("get_identity", %{})] do
      refused = mcp(body, from: from)
      assert refused.status == 401
      assert error(refused)["code"] == "agent_auth_required"
      assert get_resp_header(refused, "www-authenticate") == []
    end
  end

  test "a query string is refused for every caller before anything else runs", %{from: from} do
    for opts <- [
          [],
          [proof: wallet()],
          [proof: wallet(), signature: "forged"],
          [token: "a-token"]
        ] do
      refused = mcp(rpc("tools/list"), [from: from, query: "tool=get_identity"] ++ opts)
      assert refused.status == 400
      assert error(refused)["code"] == "unsupported_query"
    end
  end

  test "a page from another site is refused before any signature is checked", %{from: from} do
    for origin <- ["https://evil.example", "null"] do
      refused =
        mcp(rpc("tools/list"), from: from, origin: origin, proof: wallet(), signature: "forged")

      assert refused.status == 403
      assert error(refused)["code"] == "origin_not_allowed"
    end

    own = mcp(rpc("tools/list"), from: from, origin: PublicDocuments.url(""), proof: wallet())
    assert own.status == 200

    none = mcp(rpc("tools/list"), from: from, proof: wallet())
    assert none.status == 200
  end

  test "one call a request: a batch is refused", %{from: from} do
    batch = mcp([rpc("tools/list"), rpc("ping")], from: from, proof: wallet())
    assert batch.status == 400
    assert error(batch)["code"] == "batch_not_supported"
  end

  test "only POST /mcp is served; anything else answers in the site's shape", %{from: from} do
    for {method, path} <- [
          {:options, "/mcp"},
          {:put, "/mcp"},
          {:patch, "/mcp"},
          {:delete, "/mcp"},
          {:get, "/mcp"},
          {:post, "/mcp/anything"}
        ] do
      conn =
        conn(method, path, "{}")
        |> Map.put(:remote_ip, from)
        |> put_req_header("content-type", "application/json")
        |> put_req_header("accept", "application/json")
        |> @endpoint.call([])

      assert conn.status in [404, 405], "#{method} #{path}"
      assert %{"code" => _, "message" => _, "hint" => _} = error(conn)
      if conn.status == 405, do: assert(get_resp_header(conn, "allow") == ["POST"])
    end

    form =
      conn(:post, "/mcp", "jsonrpc=2.0&method=tools%2Flist")
      |> Map.put(:remote_ip, from)
      |> put_req_header("content-type", "application/x-www-form-urlencoded")
      |> put_req_header("accept", "application/json")
      |> put_req_header("x-siwa-signature", "fixture-proof")
      |> put_req_header("x-agent-wallet-address", wallet())
      |> @endpoint.call([])

    assert form.status == 415
    assert %{"code" => "unsupported_media_type", "hint" => hint} = error(form)
    assert hint =~ PublicDocuments.url("/llms.txt")

    {413, _headers, body} =
      assert_error_sent(413, fn ->
        conn(:post, "/mcp", Jason.encode!(%{"padding" => String.duplicate("a", 1_100_000)}))
        |> Map.put(:remote_ip, from)
        |> put_req_header("content-type", "application/json")
        |> put_req_header("accept", "application/json")
        |> @endpoint.call([])
      end)

    assert %{"code" => _, "message" => _, "hint" => _} = Jason.decode!(body)["error"]
  end

  test "a GET for an event stream is answered 405, and a body that is not JSON 415, whatever it accepts",
       %{from: from} do
    stream =
      conn(:get, "/mcp")
      |> Map.put(:remote_ip, from)
      |> put_req_header("accept", "text/event-stream")
      |> @endpoint.call([])

    assert stream.status == 405
    assert get_resp_header(stream, "allow") == ["POST"]
    assert %{"code" => "method_not_allowed"} = error(stream)

    form =
      conn(:post, "/mcp", "jsonrpc=2.0&method=tools%2Flist")
      |> Map.put(:remote_ip, from)
      |> put_req_header("content-type", "application/x-www-form-urlencoded")
      |> put_req_header("accept", "text/event-stream")
      |> @endpoint.call([])

    assert form.status == 415
    assert %{"code" => "unsupported_media_type"} = error(form)
  end

  test "one address gets 120 requests a minute here, as on the API", %{from: from} do
    statuses = for _ <- 1..121, do: mcp(rpc("tools/list"), from: from).status
    assert Enum.take(statuses, 120) |> Enum.uniq() == [401]
    assert List.last(statuses) == 429
  end

  test "a token that isn't checked spends the same 120 from its address, each request once",
       %{from: from} do
    statuses =
      for n <- 1..121,
          do:
            mcp(rpc("tools/list"), from: from, token: if(rem(n, 2) == 0, do: "not-a-token")).status

    assert Enum.take(statuses, 120) |> Enum.uniq() == [401]
    assert List.last(statuses) == 429
  end

  defp mcp(body, opts) do
    path = if opts[:query], do: "/mcp?" <> opts[:query], else: "/mcp"

    conn(:post, path, Jason.encode!(body))
    |> Map.put(:remote_ip, Keyword.fetch!(opts, :from))
    |> then(&if(opts[:origin], do: put_req_header(&1, "origin", opts[:origin]), else: &1))
    |> put_req_header("content-type", "application/json")
    |> put_req_header("accept", "application/json, text/event-stream")
    |> then(
      &if(opts[:proof],
        do: signed(&1, opts[:proof], opts[:signature] || "fixture-proof"),
        else: &1
      )
    )
    |> then(
      &if(opts[:token],
        do: put_req_header(&1, "authorization", "Bearer " <> opts[:token]),
        else: &1
      )
    )
    |> @endpoint.call([])
  end

  defp signed(conn, wallet, signature) do
    conn
    |> put_req_header("x-siwa-signature", signature)
    |> put_req_header("x-agent-wallet-address", wallet)
  end

  defp call(name, input),
    do: %{
      "jsonrpc" => "2.0",
      "id" => 1,
      "method" => "tools/call",
      "params" => %{"name" => name, "arguments" => %{"input" => input}}
    }

  defp rpc(method), do: %{"jsonrpc" => "2.0", "id" => 1, "method" => method}

  defp result(conn), do: Jason.decode!(conn.resp_body)["result"]
  defp error(conn), do: Jason.decode!(conn.resp_body)["error"]

  defp wallet, do: "0x" <> Base.encode16(:crypto.strong_rand_bytes(20), case: :lower)
end
