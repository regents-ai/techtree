defmodule TechtreeWeb.EnquiryLiveTest do
  # The enquiry form in the Contact section of the home page and every
  # service's page, as a visitor uses it:
  # - a service's page has its own service chosen, and the home page none;
  # - a filled-in form is kept, a note takes its place, and the team reads the
  #   enquiry under Enquiries at /admin/messages, which is not found for anyone
  #   else;
  # - each field left wrong is refused under itself, and nothing is kept;
  # - the field people never see, when filled in, shows the note and keeps
  #   nothing;
  # - past its address's allowance the form says so and keeps nothing.
  # A service's page and the team page are read as they render: they read the
  # sign-in from the socket's connect info, which the LiveView test harness does
  # not carry. Presses on a service's page in a real browser are in
  # `assets/test/browser/enquiry.spec.ts`.
  use TechtreeWeb.ConnCase, async: false

  import Phoenix.LiveViewTest

  alias Techtree.Accounts
  alias Techtree.Accounts.SessionAuthority
  alias Techtree.Actors.System
  alias Techtree.Limits
  alias Techtree.Messages.Enquiry
  alias TechtreeWeb.{ClientAddress, Services}

  @enquiry %{
    "name" => "Grace Hopper",
    "email" => "grace@example.com",
    "company" => "Compilers Ltd",
    "service" => "models",
    "goal" => "We want a smaller model that answers our support tickets as well."
  }

  # Each test sends from an address of its own, so none spends another's allowance.
  setup %{conn: conn} do
    n = :erlang.unique_integer([:positive])

    %{
      conn: %{
        conn
        | remote_ip: {10, rem(div(n, 65_536), 256), rem(div(n, 256), 256), rem(n, 256)}
      }
    }
  end

  test "a service's page has its service chosen, and the home page none", %{conn: conn} do
    for service <- Services.all() ++ [Services.security()] do
      page =
        conn |> get(Services.path(service.id)) |> html_response(200) |> LazyHTML.from_document()

      options = LazyHTML.query(page, "#contact #enquiry-service option")

      assert LazyHTML.attribute(options, "value") ==
               Enum.map(Enquiry.services(), &Atom.to_string/1)

      assert page
             |> LazyHTML.query("#enquiry-service option[selected]")
             |> LazyHTML.attribute("value") == [Atom.to_string(service.id)]
    end

    {:ok, live, _html} = live(conn, ~p"/")
    assert has_element?(live, ~s|#enquiry-service option[value=""]|)
    refute has_element?(live, "#enquiry-service option[selected]")
  end

  test "a sent enquiry is kept, and the team reads it under Enquiries", %{conn: conn} do
    {:ok, live, _html} = live(conn, ~p"/")
    live |> form("#enquiry-form", enquiry: @enquiry) |> render_submit()

    assert has_element?(live, "#enquiry-sent")
    refute has_element?(live, "#enquiry-form")
    assert [%Enquiry{service: :models} = enquiry] = enquiries()
    assert Map.take(enquiry, [:name, :email, :company, :goal]) == take(@enquiry)

    {person, account} = signed_in_account(conn)
    assert conn |> get(~p"/admin/messages?show=enquiries") |> response(404)
    assert person |> get(~p"/admin/messages?show=enquiries") |> response(404)

    put_admins([account.privy_user_id])

    team =
      person
      |> get(~p"/admin/messages?show=enquiries")
      |> html_response(200)
      |> LazyHTML.from_document()

    item = LazyHTML.query(team, "#team-enquiries #enquiry-#{enquiry.id}")
    assert LazyHTML.text(item) =~ "Grace Hopper"

    assert item |> LazyHTML.query(".team-messages__body") |> LazyHTML.text() |> String.trim() ==
             @enquiry["goal"]

    assert item |> LazyHTML.query("a") |> LazyHTML.attribute("href") == [
             "mailto:grace@example.com"
           ]

    assert Enum.empty?(LazyHTML.query(team, "#team-messages"))
  end

  test "each field left wrong is refused under itself, and nothing is kept", %{conn: conn} do
    {:ok, live, _html} = live(conn, ~p"/")

    live
    |> form("#enquiry-form",
      enquiry: %{"name" => "", "email" => "grace", "company" => "", "goal" => ""}
    )
    |> render_submit()

    for field <- ~w(name email company service goal) do
      assert has_element?(live, ~s|#enquiry-#{field}[aria-invalid="true"]|)
      assert has_element?(live, "#enquiry-#{field}-errors p")
    end

    refute has_element?(live, "#enquiry-sent")
    assert enquiries() == []
  end

  test "the field people never see, filled in, keeps nothing", %{conn: conn} do
    {:ok, live, _html} = live(conn, ~p"/")

    live
    |> form("#enquiry-form", %{"enquiry" => @enquiry, "website" => "https://example.com"})
    |> render_submit()

    assert has_element?(live, "#enquiry-sent")
    assert enquiries() == []
  end

  test "past its address's allowance the form says so and keeps nothing", %{conn: conn} do
    key = ClientAddress.client_key(conn)
    for _ <- 1..5, do: :ok = Limits.spend(:enquiry_address, key)

    {:ok, live, _html} = live(conn, ~p"/")
    live |> form("#enquiry-form", enquiry: @enquiry) |> render_submit()

    assert has_element?(live, ~s|#enquiry-form .rg-notice[role="alert"]|)
    refute has_element?(live, ~s|#enquiry-form [aria-invalid="true"]|)
    refute has_element?(live, "#enquiry-sent")
    assert enquiries() == []
  end

  defp enquiries, do: Ash.read!(Enquiry, authorize?: false)

  defp take(params),
    do: Map.new(~w(name email company goal), &{String.to_existing_atom(&1), params[&1]})

  defp signed_in_account(conn) do
    wallet = "0x" <> Base.encode16(:crypto.strong_rand_bytes(20), case: :lower)

    account =
      Accounts.register_verified!(
        "did:privy:enquiry-page-" <> Ecto.UUID.generate(),
        wallet,
        [wallet],
        actor: %System{}
      )

    {:bootstrap, claim} = SessionAuthority.renew(nil)
    {:ok, :bind, claim} = SessionAuthority.sign_in(claim, account.id)
    {Plug.Test.init_test_session(conn, SessionAuthority.session(claim)), account}
  end

  defp put_admins(admins) do
    old = Application.fetch_env(:regent_agents, :admins)
    Application.put_env(:regent_agents, :admins, admins)

    on_exit(fn ->
      case old do
        {:ok, admins} -> Application.put_env(:regent_agents, :admins, admins)
        :error -> Application.delete_env(:regent_agents, :admins)
      end
    end)
  end
end
