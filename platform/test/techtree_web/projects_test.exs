defmodule TechtreeWeb.ProjectsTest do
  # A delivered project on the site, as each reader reaches it:
  # - its owner, signed in, finds it in Projects, reads its page and downloads
  #   the package byte for byte, as a file that is never kept on the way;
  # - another person finds nothing: not in their list, not its page, not its
  #   download; a signed-out visitor is asked to sign in;
  # - the team's Projects tab is the admins' alone, and admins download any
  #   project;
  # - a withdrawn project is gone for its owner and for downloads;
  # - the owner's paired agent lists, reads and downloads the person's
  #   projects, and finds no one else's.
  # Pages are read as they first render. Presses in a real browser are in
  # `assets/test/browser/projects.spec.ts`.
  use TechtreeWeb.ConnCase, async: false

  alias Techtree.{Accounts, NetworkFixture, ProjectPackage, Projects}
  alias Techtree.Accounts.SessionAuthority
  alias Techtree.Actors.System

  setup %{conn: conn} do
    {admin_conn, admin_account} = signed_in(conn)
    put_admins([admin_account.privy_user_id])
    admin = %RegentAgents.Person{privy_user_id: admin_account.privy_user_id, role: :admin}

    {owner_conn, owner} = signed_in(conn)
    bytes = ProjectPackage.build()
    {:ok, project} = Projects.deliver_project(owner.privy_user_id, bytes, actor: admin)

    %{
      admin: admin,
      admin_conn: admin_conn,
      owner: owner,
      owner_conn: owner_conn,
      project: project,
      bytes: bytes
    }
  end

  test "its owner finds it, reads its page and downloads the exact package", context do
    %{owner_conn: conn, project: project, bytes: bytes} = context

    list = page(conn, ~p"/account/projects")

    assert attribute(list, "#project-#{project.id} a", "href") == [
             ~p"/account/projects/#{project.id}"
           ]

    page = page(conn, ~p"/account/projects/#{project.id}")

    assert attribute(page, "#project-download", "href") == [
             ~p"/account/projects/#{project.id}/package"
           ]

    assert text(page, "#project-checksum") == project.package_sha256

    assert page |> LazyHTML.query("#project-cases tbody tr") |> attribute_values("data-change") ==
             ["better", "same"]

    assert page |> LazyHTML.query("#project-candidates tbody tr") |> Enum.count() == 3
    # The report's own HTML is never run or shown as markup.
    assert page |> LazyHTML.query("#project-report script") |> Enum.empty?()
    assert page |> LazyHTML.query("#project-report strong") |> LazyHTML.text() == "5 of 6"

    download = get(conn, ~p"/account/projects/#{project.id}/package")
    assert response(download, 200) == bytes
    assert get_resp_header(download, "content-type") == ["application/gzip"]
    assert ["private, no-store"] = get_resp_header(download, "cache-control")
    assert get_resp_header(download, "x-content-type-options") == ["nosniff"]

    assert get_resp_header(download, "content-disposition") == [
             ~s(attachment; filename="refund-routing-#{binary_part(project.id, 0, 8)}.tar.gz")
           ]
  end

  test "Projects is a tab of the account, after Account, and of the team's page", context do
    account = page(context.owner_conn, ~p"/account/projects")

    assert attribute(account, ".account-shell__tabs a", "href") == [
             ~p"/account",
             ~p"/account/projects",
             ~p"/account/agents",
             ~p"/account/points",
             ~p"/account/wallets",
             ~p"/account/connections"
           ]

    assert attribute(account, ".account-shell__tabs a[aria-current=page]", "href") == [
             ~p"/account/projects"
           ]

    team = page(context.admin_conn, ~p"/admin/messages?show=projects")

    assert attribute(team, "#team-tabs a", "href") == [
             ~p"/admin/messages",
             ~p"/admin/messages?show=enquiries",
             ~p"/admin/messages?show=projects"
           ]
  end

  test "another person finds nothing, and a signed-out visitor is asked to sign in", context do
    %{conn: conn, project: project} = context
    {other, _account} = signed_in(conn)

    assert other
           |> page(~p"/account/projects")
           |> LazyHTML.query("#project-#{project.id}")
           |> Enum.empty?()

    for path <- [
          ~p"/account/projects/#{project.id}",
          ~p"/account/projects/#{project.id}/package",
          ~p"/account/projects/not-an-id",
          ~p"/account/projects/not-an-id/package",
          ~p"/account/projects/#{Ecto.UUID.generate()}"
        ] do
      assert_error_sent 404, fn -> get(other, path) end
    end

    signed_out = page(conn, ~p"/account/projects/#{project.id}")
    assert signed_out |> LazyHTML.query("#project-page-signed-out") |> Enum.count() == 1
    assert signed_out |> LazyHTML.query("#project-title") |> Enum.empty?()

    assert redirected_to(get(conn, ~p"/account/projects/#{project.id}/package")) ==
             ~p"/account/projects/#{project.id}"
  end

  test "the team's Projects tab is the admins' alone, and they download any project", context do
    %{conn: conn, admin_conn: admin_conn, owner_conn: owner_conn, project: project} = context

    assert conn |> get(~p"/admin/messages?show=projects") |> response(404)
    assert owner_conn |> get(~p"/admin/messages?show=projects") |> response(404)

    team = page(admin_conn, ~p"/admin/messages?show=projects")
    assert team |> LazyHTML.query("#team-deliver") |> Enum.count() == 1

    assert attribute(team, "#team-project-#{project.id} a[download]", "href") == [
             ~p"/account/projects/#{project.id}/package"
           ]

    assert admin_conn |> get(~p"/account/projects/#{project.id}/package") |> response(200) ==
             context.bytes
  end

  test "a withdrawn project is gone for its owner and for downloads", context do
    %{admin: admin, admin_conn: admin_conn, owner_conn: owner_conn, project: project} = context
    listed = Enum.find(Projects.list_team_projects!(actor: admin).results, &(&1.id == project.id))
    {:ok, _withdrawn} = Projects.withdraw_project(listed, actor: admin)

    assert owner_conn
           |> page(~p"/account/projects")
           |> LazyHTML.query("#project-#{project.id}")
           |> Enum.empty?()

    assert_error_sent 404, fn -> get(owner_conn, ~p"/account/projects/#{project.id}") end
    assert_error_sent 404, fn -> get(owner_conn, ~p"/account/projects/#{project.id}/package") end
    assert_error_sent 404, fn -> get(admin_conn, ~p"/account/projects/#{project.id}/package") end

    # The team still sees it, withdrawn, with nothing left to download or withdraw.
    team = page(admin_conn, ~p"/admin/messages?show=projects")
    assert team |> LazyHTML.query("#team-project-#{project.id}") |> Enum.count() == 1

    assert team
           |> LazyHTML.query("#team-project-#{project.id} .team-projects__actions")
           |> Enum.empty?()
  end

  test "the owner's paired agent lists, reads and downloads only its person's projects",
       context do
    %{owner: owner, project: project, bytes: bytes, admin: admin} = context
    agent = paired_agent(owner)

    assert %{"projects" => [listed]} =
             agent |> get(~p"/api/v1/account/projects") |> json_response(200)

    assert listed["id"] == project.id
    assert listed["verdict"] == "improved"

    whole = agent |> get(~p"/api/v1/account/projects/#{project.id}") |> json_response(200)
    assert whole["summary"]["selected"]["solved"] == 5
    refute Map.has_key?(whole["summary"], "cost_cents")
    assert whole["report_md"] == ProjectPackage.files()["report.md"]
    assert whole["package"]["sha256"] == project.package_sha256

    download = get(agent, ~p"/api/v1/account/projects/#{project.id}/package")
    assert response(download, 200) == bytes
    assert ["private, no-store"] = get_resp_header(download, "cache-control")

    {_conn, other} = signed_in(build_conn())

    {:ok, others} =
      Projects.deliver_project(other.privy_user_id, ProjectPackage.build(), actor: admin)

    for path <- [
          ~p"/api/v1/account/projects/#{others.id}",
          ~p"/api/v1/account/projects/#{others.id}/package",
          ~p"/api/v1/account/projects/not-an-id"
        ] do
      assert %{"error" => %{"code" => "project_not_found"}} =
               agent |> get(path) |> json_response(404)
    end

    assert %{"projects" => [%{"id" => id}]} =
             agent |> get(~p"/api/v1/account/projects") |> json_response(200)

    assert id == project.id
  end

  # A person signed in to the site, as a browser carries the session.
  defp signed_in(conn) do
    wallet = "0x" <> Base.encode16(:crypto.strong_rand_bytes(20), case: :lower)

    account =
      Accounts.register_verified!(
        "did:privy:projects-page-" <> Ecto.UUID.generate(),
        wallet,
        [wallet],
        actor: %System{}
      )

    {:bootstrap, claim} = SessionAuthority.renew(nil)
    {:ok, :bind, claim} = SessionAuthority.sign_in(claim, account.id)

    conn =
      conn
      |> put_req_header("accept", "text/html")
      |> Plug.Test.init_test_session(SessionAuthority.session(claim))

    {conn, account}
  end

  # An agent paired with `person`, its requests signed; the sign-in service's
  # check of the signature is answered by the fixture.
  defp paired_agent(person) do
    wallet = "0x" <> Base.encode16(:crypto.strong_rand_bytes(20), case: :lower)
    NetworkFixture.sign_as(%{wallet_address: wallet})

    code =
      RegentAgents.issue_pairing_code!(
        actor: %RegentAgents.Person{privy_user_id: person.privy_user_id}
      )

    RegentAgents.pair_agent!(code.code, "Fixture", :codex,
      actor: %RegentAgents.Agent{wallet: wallet}
    )

    build_conn() |> put_req_header("accept", "application/json") |> NetworkFixture.signed()
  end

  defp page(conn, path), do: conn |> get(path) |> html_response(200) |> LazyHTML.from_document()

  defp text(page, selector),
    do: page |> LazyHTML.query(selector) |> LazyHTML.text() |> String.trim()

  defp attribute(page, selector, name),
    do: page |> LazyHTML.query(selector) |> LazyHTML.attribute(name)

  defp attribute_values(nodes, name), do: LazyHTML.attribute(nodes, name)

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
