defmodule Techtree.ReleaseTest do
  # The release commands every site carries, run against disposable databases:
  # the launchers, the staging bootstrap, the listing of what a database and the
  # release disagree about, and the shared changes a deployment never applies.
  # The bootstrap and listing cases point the application repository at a
  # disposable database, so this module runs alone.
  use ExUnit.Case, async: false

  import ExUnit.CaptureIO

  alias Techtree.LocalDatabaseFixture
  alias Techtree.Release
  alias Techtree.Repo

  @moduletag timeout: 300_000

  @role "TECHTREE_DEPLOYMENT_ROLE"
  @role_error "bootstrap-staging requires TECHTREE_DEPLOYMENT_ROLE to be exactly staging"
  @missing_table_error "no schema_migrations table: run bootstrap-staging first"
  @unreachable [
    hostname: "127.0.0.1",
    port: 1,
    database: "techtree_refused",
    username: "nobody",
    password: nil,
    pool_size: 1
  ]

  # Two cases migrate a database from scratch inside one VM, so the same
  # migration modules are loaded more than once. That redefinition is expected
  # here and nothing else compiles while this module runs.
  setup do
    previous = Code.get_compiler_option(:ignore_module_conflict)
    Code.put_compiler_option(:ignore_module_conflict, true)
    on_exit(fn -> Code.put_compiler_option(:ignore_module_conflict, previous) end)
    :ok
  end

  test "every launcher runs its guarded command with no arguments and prints no variables" do
    for {path, command} <- [
          {"rel/overlays/bin/migrate", :migrate},
          {"rel/overlays/bin/migrate-shared", :migrate_shared},
          {"rel/overlays/bin/bootstrap-staging", :bootstrap_staging},
          {"rel/overlays/bin/pending-migrations", :pending_migrations}
        ] do
      script = File.read!(path)

      assert script ==
               """
               #!/bin/sh
               set -eu

               TECHTREE_RELEASE_COMMAND=migrate exec "$(dirname "$0")/techtree" eval 'Techtree.Release.#{command}()'
               """

      assert File.stat!(path).mode |> Bitwise.band(0o100) != 0
      assert {command, 0} in Release.__info__(:functions)
    end
  end

  test "bootstrap refuses every role but staging before it opens a connection" do
    for role <- [nil, "", "production", "Staging", "staging ", "rehearsal"] do
      getenv = fn
        @role -> role
        name -> flunk("bootstrap read #{name} before it checked the deployment role")
      end

      assert_raise RuntimeError, @role_error, fn ->
        Release.bootstrap_staging(getenv: getenv, config: @unreachable)
      end
    end
  end

  test "bootstrap prepares an empty staging database and runs every migration to completion" do
    config = bootstrapped_database()

    assert "wallet_address" in column_names(config, "regent_names", "platform_human_users")
    assert applied_versions(config) == release_versions()
    assert capture_io(fn -> Release.migrate_shared(config: config) end) == "none\n"
  end

  test "bootstrap refuses a database that already carries migration state" do
    config = bootstrapped_database()

    assert_raise RuntimeError,
                 "public.schema_migrations already exists: destroy and recreate the staging database",
                 fn -> Release.bootstrap_staging(getenv: staging_getenv(), config: config) end
  end

  test "bootstrap refuses a database that already has the regent_names schema, and changes nothing" do
    config = disposable_database()
    query!(config, "CREATE SCHEMA regent_names")

    assert_raise RuntimeError,
                 "regent_names schema already exists: destroy and recreate the staging database",
                 fn -> Release.bootstrap_staging(getenv: staging_getenv(), config: config) end

    refute migration_table?(config)
  end

  test "the listing prints none on a database the release agrees with" do
    config = bootstrapped_database()

    assert capture_io(fn -> Release.pending_migrations(config: config) end) == "none\n"
  end

  test "the listing names every version the release carries that the database has not applied" do
    config = disposable_database()
    held_back = Enum.take(release_migration_files(), -1)

    bootstrap(config, migrations_directory(release_migration_files() -- held_back))

    assert capture_io(fn -> Release.pending_migrations(config: config) end) ==
             "pending: #{Enum.map_join(held_back, " ", &version_of/1)}\n"
  end

  test "the listing names every applied version whose file the release does not carry" do
    config = bootstrapped_database()

    query!(
      config,
      "INSERT INTO public.schema_migrations (version, inserted_at) VALUES ($1, NOW()::timestamp)",
      [20_990_101_000_000]
    )

    assert capture_io(fn -> Release.pending_migrations(config: config) end) ==
             "applied-without-file: 20990101000000\n"
  end

  test "the listing refuses a database with no migration table and creates nothing" do
    config = disposable_database()

    assert_raise RuntimeError, @missing_table_error, fn ->
      Release.pending_migrations(config: config)
    end

    refute migration_table?(config)
  end

  # A shared change missing from its own ledger is what a release carrying a
  # newer shared library meets: the listing names it, and the deployment check
  # refuses and applies nothing.
  test "a missing shared change is listed and stops the deployment check" do
    config = bootstrapped_database()
    [{schema, version} | _] = applied_shared(config)
    query!(config, "DELETE FROM #{schema}.schema_migrations WHERE version = $1", [version])

    assert capture_io(fn -> Release.pending_migrations(config: config) end) ==
             "shared-pending: #{schema} #{version}\n"

    assert_raise RuntimeError,
                 "These separately approved shared migrations must be applied before deployment: #{schema} #{version}",
                 fn -> with_repo(config, &Release.require_signed_access_schema!/1) end
  end

  test "migrate-shared applies every shared change this site carries, once" do
    config = disposable_database()
    with_repo(config, fn _repo -> LocalDatabaseFixture.create_shared_tables!() end)

    assert capture_io(fn -> Release.migrate_shared(config: config) end) ==
             "applied: #{Enum.join(shipped_shared(), ", ")}\n"

    assert capture_io(fn -> Release.migrate_shared(config: config) end) == "none\n"
  end

  # Production's own schema starts from the imported history, so a database
  # whose ledger is missing an imported version stops the deployment before
  # either ledger changes.
  test "migrate refuses incomplete imported history and changes neither ledger" do
    config = disposable_database()
    query!(config, "CREATE SCHEMA techtree_app")

    query!(
      config,
      "CREATE TABLE public.schema_migrations (version bigint PRIMARY KEY, inserted_at timestamp)"
    )

    query!(config, "INSERT INTO public.schema_migrations VALUES (1, now())")

    query!(
      config,
      "CREATE TABLE techtree_app.schema_migrations (LIKE public.schema_migrations INCLUDING ALL)"
    )

    options =
      Keyword.merge(config,
        default_prefix: "techtree_app",
        migration_default_prefix: "techtree_app"
      )

    Application.put_env(:techtree, Repo, options)

    assert_raise RuntimeError,
                 "Import the complete Techtree schema and migration history before migrating",
                 fn -> Release.migrate() end

    assert Application.fetch_env!(:techtree, Repo) == options
    refute Process.whereis(Repo)
    assert query!(config, "SELECT version FROM public.schema_migrations").rows == [[1]]
    assert query!(config, "SELECT version FROM techtree_app.schema_migrations").rows == []
  end

  test "the local fixture prepares only a local dev or test database" do
    local = [hostname: "127.0.0.1", database: "techtree_test"]

    assert LocalDatabaseFixture.validate_target!(:test, local) == :ok

    assert LocalDatabaseFixture.validate_target!(:dev, Keyword.put(local, :hostname, "::1")) ==
             :ok

    for {env, repo} <- [
          {:prod, local},
          {:test, Keyword.put(local, :hostname, "db.example.com")},
          {:test, Keyword.put(local, :database, "techtree")},
          {:test, Keyword.put(local, :database, "techtree_test_copy")}
        ] do
      assert_raise RuntimeError,
                   "local human-account fixture refused unsafe database target",
                   fn ->
                     LocalDatabaseFixture.validate_target!(env, repo)
                   end
    end
  end

  defp staging_getenv do
    fn
      @role -> "staging"
      _name -> nil
    end
  end

  defp bootstrap(
         config,
         migrations_path \\ Application.app_dir(:techtree, "priv/repo/migrations")
       ) do
    Release.bootstrap_staging(
      getenv: staging_getenv(),
      config: config,
      migrations_path: migrations_path
    )
  end

  defp bootstrapped_database do
    config = disposable_database()
    bootstrap(config)
    config
  end

  # The application repository is running against the shared test database, so
  # every case that points the release commands somewhere else takes it down
  # first and puts it back exactly as it was.
  defp disposable_database do
    previous = Application.get_env(:techtree, Repo)

    config = [
      hostname: "127.0.0.1",
      port: 5432,
      database: "techtree_release_#{System.unique_integer([:positive])}",
      username: previous[:username],
      password: previous[:password],
      pool_size: 2
    ]

    :ok = Supervisor.terminate_child(Techtree.Supervisor, Repo)
    :ok = Ecto.Adapters.Postgres.storage_up(config)

    on_exit(fn ->
      Ecto.Adapters.Postgres.storage_down(config)
      Application.put_env(:techtree, Repo, previous)
      {:ok, _pid} = Supervisor.restart_child(Techtree.Supervisor, Repo)
      Ecto.Adapters.SQL.Sandbox.mode(Repo, :manual)
    end)

    config
  end

  defp migrations_directory(files) do
    directory =
      Path.join(
        System.tmp_dir!(),
        "techtree-release-migrations-#{System.unique_integer([:positive])}"
      )

    File.mkdir_p!(directory)
    on_exit(fn -> File.rm_rf!(directory) end)

    for file <- files,
        do: File.cp!(Path.join(release_migrations_path(), file), Path.join(directory, file))

    directory
  end

  defp release_migrations_path, do: Application.app_dir(:techtree, "priv/repo/migrations")

  defp release_migration_files do
    release_migrations_path()
    |> Path.join("*.exs")
    |> Path.wildcard()
    |> Enum.map(&Path.basename/1)
    |> Enum.sort()
  end

  defp release_versions, do: Enum.map(release_migration_files(), &version_of/1)

  defp version_of(file) do
    {version, "_" <> _name} = Integer.parse(file)
    version
  end

  defp applied_versions(config) do
    config
    |> query!("SELECT version FROM public.schema_migrations ORDER BY version")
    |> Map.fetch!(:rows)
    |> List.flatten()
  end

  # Every shared ledger's newest applied change, one per shared schema.
  defp applied_shared(config) do
    for schema <- ~w(regent_identity regent_agents regent_credits regent_points regent_payments),
        query!(config, "SELECT to_regclass($1) IS NOT NULL", ["#{schema}.schema_migrations"]).rows ==
          [[true]],
        %{rows: [[version]]} =
          query!(config, "SELECT max(version) FROM #{schema}.schema_migrations"),
        do: {schema, version}
  end

  # Every change the shared libraries this site carries ship, as the release
  # names them, in the order they apply.
  defp shipped_shared do
    for app <- [:regent_identity, :regent_agents, :regent_credits, :regent_points],
        file <-
          app
          |> Application.app_dir("priv/repo/migrations")
          |> Path.join("*.exs")
          |> Path.wildcard()
          |> Enum.sort(),
        do: "#{app} #{file |> Path.basename() |> version_of()}"
  end

  defp column_names(config, schema, table) do
    config
    |> query!(
      "SELECT column_name FROM information_schema.columns WHERE table_schema = $1 AND table_name = $2 ORDER BY column_name",
      [schema, table]
    )
    |> Map.fetch!(:rows)
    |> List.flatten()
  end

  defp migration_table?(config) do
    query!(config, "SELECT to_regclass('public.schema_migrations') IS NOT NULL").rows ==
      [[true]]
  end

  defp query!(config, sql, params \\ []) do
    with_repo(config, &Ecto.Adapters.SQL.query!(&1, sql, params))
  end

  defp with_repo(config, fun) do
    previous = Application.get_env(:techtree, Repo)
    Application.put_env(:techtree, Repo, config)

    try do
      {:ok, result, _started} = Ecto.Migrator.with_repo(Repo, fun)
      result
    after
      Application.put_env(:techtree, Repo, previous)
    end
  end
end
