defmodule TechtreeWeb.MessagesPagesTest do
  # The Agent Message button and its window on the Watchdog offer, as the page
  # renders:
  # - the button opens the window, which holds the three texts
  #   `AgentMessage.texts/1` gives for the topic `watchdog`, each with its copy
  #   button, naming the tool and the command the site publishes;
  # - a visitor sees no form, and a signed-in person sees one;
  # - the offer's Markdown tells an agent the same three ways;
  # - no other offer has the button;
  # - /admin/messages shows the team every message, newest first, and is the
  #   not-found page for anyone who is not one of the site's admins.
  # The form's own presses are in the browser tests
  # (`assets/test/browser/agent_message.spec.ts`): the page reads the sign-in
  # from the socket's connect info, which the LiveView test harness does not carry.
  use TechtreeWeb.ConnCase, async: false

  alias Techtree.Accounts
  alias Techtree.Accounts.SessionAuthority
  alias Techtree.Actors.System
  alias TechtreeWeb.Components.AgentMessage

  @window "#watchdog-message"

  test "the Watchdog offer's button opens a window with the three texts", %{conn: conn} do
    page = page(conn, ~p"/services/watchdog")

    assert [button] =
             page
             |> LazyHTML.query("#contact [data-agent-message-open]")
             |> LazyHTML.attribute("aria-controls")

    assert "#" <> button == @window

    for %{id: id, text: text} <- AgentMessage.texts("watchdog") do
      assert page |> LazyHTML.query("#{@window}-text-#{id}") |> LazyHTML.text() == text

      assert page
             |> LazyHTML.query(~s|#{@window} [data-copy-target="watchdog-message-text-#{id}"]|)
             |> Enum.count() == 1
    end

    assert page |> LazyHTML.query("#{@window} [data-copy-target]") |> Enum.count() == 3
  end

  test "the texts name the tool, the command and the address the site publishes", %{conn: conn} do
    manifest = conn |> get(~p"/capabilities.json") |> json_response(200)
    tool = Enum.find(manifest["tools"], &(&1["operation_id"] == "leaveMessage"))
    command = String.replace(tool["interfaces"]["cli"]["command"], "<topic>", "watchdog")
    [cli, mcp, webmcp] = Enum.map(AgentMessage.texts("watchdog"), & &1.text)

    assert cli =~ "regents #{manifest["cli"]["namespace"]} #{command}"
    assert mcp =~ "#{TechtreeWeb.PublicDocuments.url("/mcp")}. Call its #{tool["name"]} tool"
    assert webmcp =~ "the WebMCP tool #{tool["name"]}"

    for text <- [mcp, webmcp] do
      [input] = Regex.run(~r/\{.*\}/s, text)
      assert Map.keys(Jason.decode!(input)) -- tool["input_schema"]["required"] == ["reply_to"]
    end
  end

  test "a visitor sees no form, and a signed-in person sees one", %{conn: conn} do
    visitor = page(conn, ~p"/services/watchdog")
    assert Enum.empty?(LazyHTML.query(visitor, "#{@window} form"))

    person = page(signed_in(conn), ~p"/services/watchdog")
    assert [_form] = Enum.to_list(LazyHTML.query(person, "#{@window}-person-form"))
    assert [_body] = Enum.to_list(LazyHTML.query(person, "#{@window}-person-form textarea"))
  end

  test "the offer's Markdown tells an agent the same three ways", %{conn: conn} do
    text =
      conn
      |> put_req_header("accept", "text/markdown")
      |> get(~p"/services/watchdog")
      |> response(200)

    for %{text: way} <- AgentMessage.texts("watchdog"), do: assert(text =~ way)
    refute text =~ "{{"
  end

  test "no other offer has the button", %{conn: conn} do
    for path <- [~p"/services/verify", ~p"/services/cyber-assist"] do
      page = page(conn, path)
      assert Enum.empty?(LazyHTML.query(page, "[data-agent-message-open], [data-agent-message]"))
    end
  end

  test "/admin/messages shows the team every message, and is not found for anyone else",
       %{conn: conn} do
    {person, account} = signed_in_account(conn)
    {:ok, older} = leave(account, "agents", "First")
    {:ok, newer} = leave(account, "watchdog", "Second")

    assert conn |> get(~p"/admin/messages") |> response(404)
    assert person |> get(~p"/admin/messages") |> response(404)

    old = Application.fetch_env(:regent_agents, :admins)
    Application.put_env(:regent_agents, :admins, [account.privy_user_id])

    on_exit(fn ->
      case old do
        {:ok, value} -> Application.put_env(:regent_agents, :admins, value)
        :error -> Application.delete_env(:regent_agents, :admins)
      end
    end)

    page = page(person, ~p"/admin/messages")
    ids = page |> LazyHTML.query("#team-messages > li") |> LazyHTML.attribute("id")
    assert ids == ["message-#{newer.id}", "message-#{older.id}"]

    assert page |> LazyHTML.query("#message-#{newer.id} .team-messages__body") |> LazyHTML.text() ==
             "Second"
  end

  defp leave(account, topic, body),
    do:
      Techtree.Messages.leave_message(%{topic: topic, body: body},
        actor: Techtree.Actors.Human.for_account(account),
        context: %{client_key: Ecto.UUID.generate()}
      )

  defp page(conn, path), do: conn |> get(path) |> html_response(200) |> LazyHTML.from_document()

  defp signed_in(conn), do: conn |> signed_in_account() |> elem(0)

  defp signed_in_account(conn) do
    wallet = "0x" <> Base.encode16(:crypto.strong_rand_bytes(20), case: :lower)

    account =
      Accounts.register_verified!(
        "did:privy:message-page-" <> Ecto.UUID.generate(),
        wallet,
        [wallet],
        actor: %System{}
      )

    {:bootstrap, claim} = SessionAuthority.renew(nil)
    {:ok, :bind, claim} = SessionAuthority.sign_in(claim, account.id)
    {Plug.Test.init_test_session(conn, SessionAuthority.session(claim)), account}
  end
end
