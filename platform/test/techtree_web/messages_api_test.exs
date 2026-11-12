defmodule TechtreeWeb.MessagesApiTest do
  # An agent leaving a message for Techtree's team over signed HTTP
  # (`POST /api/v1/messages/{topic}`) and the hosted MCP tool `messages_leave`:
  # - a signed agent leaves one and gets its receipt, 201, as itself whatever
  #   the body says about the sender;
  # - its operation_id answers 200 with the first receipt, through either door,
  #   and 409 idempotency_conflict for other text;
  # - an unsigned request leaves nothing;
  # - input the action cannot take is 422 invalid_message with details, through
  #   either door;
  # - each address leaves 30 an hour through either door, counted by the address
  #   the request came from.
  # The sign-in service is stubbed: it vouches for the wallet a request names when
  # the request carries the fixture proof. Each test calls from its own address.
  use ExUnit.Case, async: false

  import Plug.Conn
  import Plug.Test

  alias Techtree.Messages.Message
  alias Techtree.Repo

  @endpoint TechtreeWeb.Endpoint

  setup do
    owner = Ecto.Adapters.SQL.Sandbox.start_owner!(Repo, shared: true)
    on_exit(fn -> Ecto.Adapters.SQL.Sandbox.stop_owner(owner) end)

    Req.Test.stub(RegentAgents.Broker, fn conn ->
      {:ok, body, conn} = read_body(conn)
      headers = Jason.decode!(body)["headers"]
      wallet = headers["x-agent-wallet-address"]

      if headers["x-siwa-signature"] == "fixture-proof" do
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
        |> Req.Test.json(%{error: %{code: "http_signature_invalid", message: "No", hint: "Sign"}})
      end
    end)

    %{from: {10, :rand.uniform(250), :rand.uniform(250), :rand.uniform(250)}, agent: wallet()}
  end

  test "a signed agent leaves a message as itself, and its operation_id answers it again",
       %{from: from, agent: agent} do
    key = Ecto.UUID.generate()

    body = %{
      body: "Hello team",
      reply_to: "agent@example.com",
      operation_id: key,
      agent_id: Ecto.UUID.generate(),
      sender_name: "Someone else"
    }

    left = http(from, agent, "watchdog", body)
    assert left.status == 201
    assert get_resp_header(left, "cache-control") == ["no-store"]
    assert %{"receipt" => %{"id" => id, "topic" => "watchdog", "inserted_at" => _}} = json(left)

    message = Ash.get!(Message, id, authorize?: false)
    assert {message.body, message.reply_to} == {"Hello team", "agent@example.com"}

    assert Ash.load!(message, :agent, authorize?: false).agent.wallet_address == agent

    assert message.sender_name == RegentFormat.short_address(agent)

    again = http(from, agent, "watchdog", body)
    assert again.status == 200
    assert json(again)["receipt"]["id"] == id

    through_mcp =
      mcp(from, agent, %{
        topic: "watchdog",
        body: "Hello team",
        reply_to: "agent@example.com",
        operation_id: key
      })

    assert %{
             "isError" => false,
             "structuredContent" => %{"replayed" => true, "receipt" => %{"id" => ^id}}
           } = through_mcp

    other = http(from, agent, "watchdog", %{body: "Other text", operation_id: key})
    assert other.status == 409
    assert %{"code" => "idempotency_conflict", "message" => _, "hint" => _} = json(other)["error"]

    assert %{"isError" => true, "content" => [%{"text" => text}]} =
             mcp(from, agent, %{topic: "watchdog", body: "Other text", operation_id: key})

    assert Jason.decode!(text)["error"]["code"] == "idempotency_conflict"
  end

  test "the hosted tool leaves a message, and refuses input the action cannot take with HTTP's code",
       %{from: from, agent: agent} do
    assert %{
             "isError" => false,
             "structuredContent" => %{"replayed" => false, "receipt" => %{"id" => id}}
           } =
             mcp(from, agent, %{
               topic: "watchdog",
               body: "From MCP",
               operation_id: Ecto.UUID.generate()
             })

    assert %Message{topic: "watchdog", body: "From MCP"} =
             Ash.get!(Message, id, authorize?: false)

    too_long = %{
      topic: "watchdog",
      body: String.duplicate("a", 2001),
      operation_id: Ecto.UUID.generate()
    }

    assert %{"isError" => true, "content" => [%{"text" => text}]} = mcp(from, agent, too_long)

    assert %{"code" => "invalid_message", "details" => [%{"field" => "body"}]} =
             Jason.decode!(text)["error"]

    refused = http(from, agent, "watchdog", Map.delete(too_long, :topic))
    assert refused.status == 422

    assert %{"code" => "invalid_message", "details" => [%{"field" => "body"}]} =
             json(refused)["error"]

    for {topic, input} <- [
          {"Watchdog!", %{body: "Hi", operation_id: Ecto.UUID.generate()}},
          {"watchdog", %{body: "Hi"}},
          {"watchdog", %{body: "Hi", operation_id: "not-a-uuid"}}
        ] do
      refused = http(from, agent, topic, input)
      assert refused.status == 422, inspect({topic, input})
      assert %{"code" => "invalid_message", "details" => [_ | _]} = json(refused)["error"]
    end

    assert [_only] = Ash.read!(Message, authorize?: false)
  end

  test "an unsigned or forged request leaves nothing", %{from: from, agent: agent} do
    body = %{body: "Hi", operation_id: Ecto.UUID.generate()}
    count = length(Ash.read!(Message, authorize?: false))

    unsigned =
      conn(:post, "/api/v1/messages/watchdog", Jason.encode!(body))
      |> Map.put(:remote_ip, from)
      |> put_req_header("content-type", "application/json")
      |> @endpoint.call([])

    assert unsigned.status == 401
    assert http(from, agent, "watchdog", body, "forged").status == 401
    assert length(Ash.read!(Message, authorize?: false)) == count
  end

  test "one address leaves 30 messages an hour through either door, whoever signs",
       %{from: from} do
    for n <- 1..30 do
      body = %{body: "Message #{n}", operation_id: Ecto.UUID.generate()}

      if rem(n, 2) == 0,
        do: assert(http(from, wallet(), "watchdog", body).status == 201),
        else:
          assert(%{"isError" => false} = mcp(from, wallet(), Map.put(body, :topic, "watchdog")))
    end

    late = %{body: "One more", operation_id: Ecto.UUID.generate()}
    refused = http(from, wallet(), "watchdog", late)
    assert refused.status == 422

    assert %{"code" => "invalid_message", "details" => [%{"field" => "body"}]} =
             json(refused)["error"]

    assert %{"isError" => true} = mcp(from, wallet(), Map.put(late, :topic, "watchdog"))

    elsewhere = {10, 251, 251, :rand.uniform(250)}
    assert http(elsewhere, wallet(), "watchdog", late).status == 201
  end

  defp http(from, wallet, topic, body, signature \\ "fixture-proof") do
    conn(:post, "/api/v1/messages/#{topic}", Jason.encode!(body))
    |> Map.put(:remote_ip, from)
    |> put_req_header("content-type", "application/json")
    |> put_req_header("x-siwa-signature", signature)
    |> put_req_header("x-agent-wallet-address", wallet)
    |> @endpoint.call([])
  end

  defp mcp(from, wallet, input) do
    call = %{
      "jsonrpc" => "2.0",
      "id" => 1,
      "method" => "tools/call",
      "params" => %{"name" => "messages_leave", "arguments" => %{"input" => input}}
    }

    conn(:post, "/mcp", Jason.encode!(call))
    |> Map.put(:remote_ip, from)
    |> put_req_header("content-type", "application/json")
    |> put_req_header("accept", "application/json, text/event-stream")
    |> put_req_header("x-siwa-signature", "fixture-proof")
    |> put_req_header("x-agent-wallet-address", wallet)
    |> @endpoint.call([])
    |> json()
    |> Map.fetch!("result")
  end

  defp json(conn), do: Jason.decode!(conn.resp_body)
  defp wallet, do: "0x" <> Base.encode16(:crypto.strong_rand_bytes(20), case: :lower)
end
