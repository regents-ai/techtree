defmodule TechtreeWeb.WatchdogLiveTest do
  @moduledoc """
  The signed-in Watchdog page as it renders: a visitor is asked to sign in and
  sees no form, and a signed-in person sees their sites with each one's proof
  record and state and the addresses on them. The actions behind the buttons
  are exercised in `Techtree.WatchdogTest`; this page has no connected walk yet
  because the account session reads its authority from the socket's connect
  info, which the LiveView test harness does not carry (feature map gap).
  """

  use TechtreeWeb.ConnCase, async: false

  alias Techtree.Accounts.SessionAuthority
  alias Techtree.Actors.Human
  alias Techtree.Repo
  alias Techtree.Watchdog
  alias Techtree.Watchdog.Ownership
  alias Techtree.WatchdogFixture

  @wallet "0x" <> String.duplicate("c", 40)

  test "a visitor is asked to sign in and sees no add form", %{conn: conn} do
    html = conn |> get(~p"/watchdog") |> html_response(200)

    assert html =~ "watchdog-signed-out"
    refute html =~ "phx-submit=\"add_site\""
  end

  test "a signed-in person with no sites sees the add form and the empty state", %{conn: conn} do
    {conn, _actor} = signed_in(conn)
    html = conn |> get(~p"/watchdog") |> html_response(200)

    assert html =~ "Add a site"
    assert html =~ "phx-submit=\"add_site\""
    assert html =~ "No sites yet"
  end

  test "each site shows its proof record and state, and its addresses", %{conn: conn} do
    {conn, actor} = signed_in(conn)

    {:ok, host} = Watchdog.add_host("example.com", %{ownership_method: :dns_txt}, actor: actor)
    {:ok, _route} = Watchdog.add_route(host.id, %{url: "https://example.com/pay"}, actor: actor)

    html = conn |> get(~p"/watchdog") |> html_response(200)

    assert html =~ "example.com"
    assert html =~ Ownership.record_value(host)
    assert html =~ "Record name"
    assert html =~ "Not proven"
    assert html =~ "https://example.com/pay"
    assert html =~ "Off"
  end

  test "a proven site shows as proven", %{conn: conn} do
    {conn, actor} = signed_in(conn)
    {:ok, host} = Watchdog.add_host("proven.example", %{ownership_method: :dns_txt}, actor: actor)

    WatchdogFixture.stub_ownership(fn req ->
      Req.Test.json(req, %{
        "Answer" => [%{"type" => 16, "data" => ~s("#{Ownership.record_value(host)}")}]
      })
    end)

    {:ok, _proven} = Ash.update(host, %{}, action: :check_ownership, actor: actor)

    html = conn |> get(~p"/watchdog") |> html_response(200)
    assert html =~ "Proven"
  end

  defp signed_in(conn) do
    %{rows: [[id]]} =
      Repo.query!(
        """
        INSERT INTO regent_names.platform_human_users
          (privy_user_id, wallet_address, wallet_addresses, created_at, updated_at)
        VALUES ('did:privy:watchdog-live-test', $1, $2, now(), now())
        RETURNING id
        """,
        [@wallet, [@wallet]]
      )

    {:bootstrap, claim} = SessionAuthority.renew(nil)
    {:ok, :bind, claim} = SessionAuthority.sign_in(claim, id)

    conn = Plug.Test.init_test_session(conn, SessionAuthority.session(claim))
    {conn, %Human{human_account_id: id, name: "tester", wallet_addresses: [@wallet]}}
  end
end
