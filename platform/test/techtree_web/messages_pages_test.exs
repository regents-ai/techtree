defmodule TechtreeWeb.MessagesPagesTest do
  # The Agent Message button and its window on the Watchdog offer, as the page
  # renders:
  # - the button opens the window, which holds the three texts
  #   `AgentMessage.texts/1` gives for the topic `watchdog`, each with its copy
  #   button, naming the tool and the command the site publishes;
  # - a visitor sees no form, and a signed-in person sees one;
  # - the offer's Markdown tells an agent the same three ways;
  # - no other offer has the button.
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
             |> LazyHTML.query(".service-offer__start [data-agent-message-open]")
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

  defp page(conn, path), do: conn |> get(path) |> html_response(200) |> LazyHTML.from_document()

  defp signed_in(conn) do
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
    Plug.Test.init_test_session(conn, SessionAuthority.session(claim))
  end
end
