defmodule TechtreeWeb.AccountMenuLiveTest do
  use TechtreeWeb.ConnCase, async: true

  alias Techtree.Accounts.SessionAuthority
  alias Techtree.Repo

  @wallet "0x" <> String.duplicate("b", 40)

  test "signed out, every page's header offers Sign in and no account menu or pairing window",
       %{conn: conn} do
    for page <- ["/", "/docs", "/results", "/account", "/about"] do
      header = conn |> get(page) |> html_response(200) |> header()

      assert Enum.count(header) == 1
      assert count(header, ~s|#account-control [data-account-target="sign-in"]|) == 1
      assert count(header, "#account-menu") == 0
      assert count(header, "#shell-pairing") == 0
    end
  end

  test "signed in, the name opens the account menu: agents, Pair New Agent, Manage Account and Sign out",
       %{conn: conn} do
    conn = signed_in(conn)

    for page <- ["/", "/docs", "/account", "/about"] do
      header = conn |> get(page) |> html_response(200) |> header()

      assert count(header, ~s|#account-chip[popovertarget="account-menu"]|) == 1
      assert count(header, "#account-menu[popover]") == 1
      assert count(header, "#account-menu #shell-agents") == 1
      pair = ~s|#account-menu button[data-pair-open][aria-controls="shell-pairing"]|
      assert count(header, pair) == 1
      assert count(header, ~s|#account-menu a[href="/account"]|) == 1
      assert count(header, ~s|#account-menu [data-account-target="sign-out"]|) == 1
    end
  end

  test "signed in, every page holds the one pairing window, and the Agents page's Pair New Agent opens it",
       %{conn: conn} do
    conn = signed_in(conn)

    for page <- ["/", "/docs", "/account/agents", "/about"] do
      header = conn |> get(page) |> html_response(200) |> header()
      assert count(header, "dialog#shell-pairing #shell-pairing-box") == 1
    end

    agents = conn |> get("/account/agents") |> html_response(200) |> LazyHTML.from_document()
    opener = ~s|#account-agents button[data-pair-open][aria-controls="shell-pairing"]|
    assert agents |> LazyHTML.query(opener) |> Enum.count() == 1
  end

  defp header(html), do: html |> LazyHTML.from_document() |> LazyHTML.query(".masthead__account")

  defp count(header, selector), do: header |> LazyHTML.query(selector) |> Enum.count()

  defp signed_in(conn) do
    %{rows: [[id]]} =
      Repo.query!(
        """
        INSERT INTO regent_names.platform_human_users
          (privy_user_id, wallet_address, wallet_addresses, created_at, updated_at)
        VALUES ('did:privy:account-menu-test', $1, $2, now(), now())
        RETURNING id
        """,
        [@wallet, [@wallet]]
      )

    {:bootstrap, claim} = SessionAuthority.renew(nil)
    {:ok, :bind, claim} = SessionAuthority.sign_in(claim, id)

    Plug.Test.init_test_session(conn, SessionAuthority.session(claim))
  end
end
