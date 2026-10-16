defmodule TechtreeWeb.SidePanelLiveTest do
  use TechtreeWeb.ConnCase, async: true

  alias Techtree.Accounts.SessionAuthority
  alias Techtree.Repo

  @wallet "0x" <> String.duplicate("b", 40)

  test "signed out, every page's header offers Sign in and no side panel", %{conn: conn} do
    for page <- ["/", "/docs", "/results", "/account", "/about"] do
      panel = conn |> get(page) |> html_response(200) |> panel()

      assert Enum.count(panel) == 1
      assert count(panel, ~s|#account-control [data-account-target="sign-in"]|) == 1
      assert count(panel, "#shell-aside") == 0
    end
  end

  test "signed in, the name opens a panel to sign out, manage the account and pair an agent",
       %{conn: conn} do
    conn = signed_in(conn)

    for page <- ["/", "/docs", "/account", "/about"] do
      panel = conn |> get(page) |> html_response(200) |> panel()

      assert count(panel, ~s|#account-chip[aria-controls="shell-aside"]|) == 1
      assert count(panel, ~s|#shell-aside [data-account-target="sign-out"]|) == 1
      assert count(panel, ~s|#shell-aside a[href="https://regents.sh/account"]|) == 1
      assert count(panel, ~s|#shell-aside a[href="/account"]|) == 1
      assert count(panel, "#shell-pairing-box") == 1
      assert count(panel, "#shell-agents") == 1
    end
  end

  defp panel(html), do: html |> LazyHTML.from_document() |> LazyHTML.query(".masthead__account")

  defp count(panel, selector), do: panel |> LazyHTML.query(selector) |> Enum.count()

  defp signed_in(conn) do
    %{rows: [[id]]} =
      Repo.query!(
        """
        INSERT INTO regent_names.platform_human_users
          (privy_user_id, wallet_address, wallet_addresses, created_at, updated_at)
        VALUES ('did:privy:side-panel-test', $1, $2, now(), now())
        RETURNING id
        """,
        [@wallet, [@wallet]]
      )

    {:bootstrap, claim} = SessionAuthority.renew(nil)
    {:ok, :bind, claim} = SessionAuthority.sign_in(claim, id)

    Plug.Test.init_test_session(conn, SessionAuthority.session(claim))
  end
end
