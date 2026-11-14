defmodule Techtree.Projects.ProjectTest do
  # Projects through the actions the pages call:
  # - an admin delivers a package to a customer found by wallet or Privy id,
  #   and who delivered it is kept;
  # - only its owner reads it: another person's list is empty and their reads
  #   find nothing, and only the download reads carry the package's bytes;
  # - only admins deliver, find customers, list every project and withdraw;
  # - a bad package or an unknown customer keeps nothing, and a package is
  #   delivered to a customer once while that delivery stands;
  # - a withdrawn project is gone for its owner, its contents are deleted, and
  #   the team's list still shows it, with who withdrew it.
  use ExUnit.Case, async: false

  alias Techtree.{Accounts, ProjectPackage, Projects, Repo}
  alias Techtree.Actors.{Human, System}
  alias Techtree.Projects.Project

  setup do
    :ok = Ecto.Adapters.SQL.Sandbox.checkout(Repo)

    admin_account = account("admin")
    put_admins([admin_account.privy_user_id])
    admin = %RegentAgents.Person{privy_user_id: admin_account.privy_user_id, role: :admin}

    %{admin: admin, admin_account: admin_account, customer: account("customer")}
  end

  test "an admin delivers a package, and only its owner reads it", context do
    %{admin: admin, admin_account: admin_account, customer: customer} = context
    bytes = ProjectPackage.build()

    assert {:ok, %Project{id: id} = project} =
             Projects.deliver_project(checksummed(customer.wallet_address), bytes, actor: admin)

    assert project.human_account_id == customer.id
    assert project.delivered_by_id == admin_account.id
    assert project.delivered_by_name == Human.for_account(admin_account).name
    assert project.customer_name == Human.for_account(customer).name

    assert {project.title, project.line, project.verdict} ==
             {"Refund routing", :skills, :improved}

    owner = Human.for_account(customer)
    assert [%Project{id: ^id} = listed] = Projects.list_my_projects!(actor: owner)

    for field <- [:package, :manifest, :report_md],
        do: assert(%Ash.NotLoaded{} = Map.get(listed, field))

    assert {:ok, %Project{id: ^id, package: %Ash.NotLoaded{}} = read} =
             Projects.get_my_project(id, actor: owner)

    assert read.manifest["summary"]["selected"]["solved"] == 5
    assert read.report_md == ProjectPackage.files()["report.md"]
    assert {:ok, %Project{package: ^bytes}} = Projects.get_my_package(id, actor: owner)

    other = Human.for_account(account("other"))
    assert {:ok, []} = Projects.list_my_projects(actor: other)
    assert {:ok, nil} = Projects.get_my_project(id, actor: other)
    assert {:ok, nil} = Projects.get_my_package(id, actor: other)
  end

  test "only admins deliver, find customers, list every project and withdraw", context do
    %{admin: admin, customer: customer} = context

    {:ok, project} =
      Projects.deliver_project(customer.privy_user_id, ProjectPackage.build(), actor: admin)

    for reader <- [
          Human.for_account(customer),
          %System{},
          %RegentAgents.Person{privy_user_id: admin.privy_user_id},
          %RegentAgents.Person{privy_user_id: "did:privy:not-listed", role: :admin},
          nil
        ] do
      package = ProjectPackage.build(manifest: &Map.put(&1, "title", "Another project"))

      assert {:error, %Ash.Error.Forbidden{}} =
               Projects.deliver_project(customer.privy_user_id, package, actor: reader)

      assert {:error, %Ash.Error.Forbidden{}} = Projects.list_team_projects(actor: reader)

      assert {:error, %Ash.Error.Forbidden{}} =
               Projects.get_team_package(project.id, actor: reader)

      assert {:error, %Ash.Error.Forbidden{}} =
               Projects.find_customer(customer.privy_user_id, actor: reader)

      assert {:error, %Ash.Error.Forbidden{}} = Projects.withdraw_project(project, actor: reader)
    end

    assert [%{withdrawn_at: nil}] = stored()
  end

  test "a customer is found by a wallet they signed in with, in any case, or their Privy id",
       %{admin: admin} do
    first = wallet()
    second = wallet()

    customer =
      Accounts.register_verified!(
        "did:privy:projects-" <> Ecto.UUID.generate(),
        first,
        [first, second],
        actor: %System{}
      )

    for found <- [first, checksummed(second), "  " <> customer.privy_user_id <> "\n"] do
      assert {:ok, %{id: id}} = Projects.find_customer(found, actor: admin)
      assert id == customer.id
    end

    for unknown <- [wallet(), "did:privy:nobody", "ada@example.com", "0x1234", "  "] do
      assert {:ok, nil} = Projects.find_customer(unknown, actor: admin)
    end
  end

  test "a bad package or an unknown customer keeps nothing", %{admin: admin, customer: customer} do
    bad = ProjectPackage.build(manifest: &Map.put(&1, "schema", "uplift-package/2"))

    assert {:error, %Ash.Error.Invalid{}} =
             Projects.deliver_project(customer.privy_user_id, bad, actor: admin)

    assert {:error, %Ash.Error.Invalid{}} =
             Projects.deliver_project(wallet(), ProjectPackage.build(), actor: admin)

    assert stored() == []
  end

  test "a package is delivered to a customer once while that delivery stands", context do
    %{admin: admin, customer: customer} = context
    bytes = ProjectPackage.build()

    assert {:ok, first} = Projects.deliver_project(customer.privy_user_id, bytes, actor: admin)

    assert {:error, %Ash.Error.Invalid{}} =
             Projects.deliver_project(customer.privy_user_id, bytes, actor: admin)

    assert {:ok, _another} =
             Projects.deliver_project(account("second").privy_user_id, bytes, actor: admin)

    {:ok, _withdrawn} = Projects.withdraw_project(team_project(admin, first.id), actor: admin)
    assert {:ok, _again} = Projects.deliver_project(customer.privy_user_id, bytes, actor: admin)
    assert length(stored()) == 3
  end

  test "a withdrawn project is gone for its owner, and only what the team's page shows stays",
       context do
    %{admin: admin, admin_account: admin_account, customer: customer} = context
    bytes = ProjectPackage.build()
    {:ok, %{id: id}} = Projects.deliver_project(customer.privy_user_id, bytes, actor: admin)

    assert {:ok, withdrawn} = Projects.withdraw_project(team_project(admin, id), actor: admin)
    assert withdrawn.withdrawn_by_id == admin_account.id
    assert withdrawn.withdrawn_by_name == Human.for_account(admin_account).name

    owner = Human.for_account(customer)
    assert {:ok, []} = Projects.list_my_projects(actor: owner)
    assert {:ok, nil} = Projects.get_my_project(id, actor: owner)
    assert {:ok, nil} = Projects.get_my_package(id, actor: owner)
    assert {:ok, nil} = Projects.get_team_package(id, actor: admin)

    assert [stored] = stored()
    assert %{package: nil, manifest: nil, report_md: nil} = stored
    assert stored.title == "Refund routing"
    assert stored.package_sha256 == sha256(bytes)
    assert stored.package_size == byte_size(bytes)

    team = team_project(admin, id)
    assert %DateTime{} = team.withdrawn_at

    assert {:error, %Ash.Error.Invalid{}} = Projects.withdraw_project(team, actor: admin)
  end

  test "the team's list never carries the package, and its download does",
       %{admin: admin} = context do
    bytes = ProjectPackage.build()

    {:ok, %{id: id}} =
      Projects.deliver_project(context.customer.privy_user_id, bytes, actor: admin)

    assert %{results: [%Project{id: ^id} = listed]} = Projects.list_team_projects!(actor: admin)

    for field <- [:package, :manifest, :report_md],
        do: assert(%Ash.NotLoaded{} = Map.get(listed, field))

    assert {:ok, %Project{package: ^bytes}} = Projects.get_team_package(id, actor: admin)
  end

  defp team_project(admin, id),
    do: Enum.find(Projects.list_team_projects!(actor: admin).results, &(&1.id == id))

  # Every project as the table holds it, contents included.
  defp stored do
    %{rows: rows, columns: columns} =
      Repo.query!(
        "SELECT title, package, manifest, report_md, package_sha256, package_size, withdrawn_at FROM projects"
      )

    columns = Enum.map(columns, &String.to_existing_atom/1)
    Enum.map(rows, &Map.new(Enum.zip(columns, &1)))
  end

  defp account(kind) do
    address = wallet()
    did = "did:privy:projects-#{kind}-" <> Ecto.UUID.generate()
    Accounts.register_verified!(did, address, [address], actor: %System{})
  end

  defp wallet, do: "0x" <> Base.encode16(:crypto.strong_rand_bytes(20), case: :lower)

  # A wallet in capitals, as a checksummed one has some.
  defp checksummed("0x" <> digits), do: "0x" <> String.upcase(digits)

  defp sha256(bytes), do: :sha256 |> :crypto.hash(bytes) |> Base.encode16(case: :lower)

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
