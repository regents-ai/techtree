defmodule Techtree.ReleaseMigrationTest do
  use ExUnit.Case, async: false

  alias Techtree.{Release, Repo}

  setup do
    previous = Application.fetch_env!(:techtree, Repo)
    direct = System.get_env("DATABASE_DIRECT_URL")

    on_exit(fn ->
      Application.put_env(:techtree, Repo, previous)

      if direct,
        do: System.put_env("DATABASE_DIRECT_URL", direct),
        else: System.delete_env("DATABASE_DIRECT_URL")
    end)

    :ok
  end

  test "direct credentials replace runtime endpoints while retaining schema and TLS" do
    config = Application.fetch_env!(:techtree, Repo)

    Application.put_env(
      :techtree,
      Repo,
      Keyword.merge(config,
        url: "postgres://runtime:private@runtime.invalid/runtime",
        socket_dir: "/unusable",
        endpoints: [{"runtime.invalid", 5432}],
        default_prefix: "techtree_app",
        migration_default_prefix: "techtree_app",
        ssl: [verify: :verify_peer]
      )
    )

    selected =
      Release.migration_config!(Repo, fn "DATABASE_DIRECT_URL" ->
        "postgresql://migration:fixture@127.0.0.1:55438/selected"
      end)

    assert selected[:username] == "migration"
    assert selected[:database] == "selected"
    assert selected[:hostname] == "127.0.0.1"
    assert selected[:port] == 55_438
    assert selected[:ssl] == [verify: :verify_peer]
    assert selected[:default_prefix] == "techtree_app"
    assert selected[:migration_default_prefix] == "techtree_app"
    refute Keyword.has_key?(selected, :url)
    refute Keyword.has_key?(selected, :socket_dir)
    refute Keyword.has_key?(selected, :endpoints)

    assert Release.migration_config!(Repo, fn "DATABASE_DIRECT_URL" ->
             "postgresql://migration:fixture@127.0.0.1/selected"
           end)[:port] == 5432
  end

  test "missing or malformed direct credentials fail without disclosing their value" do
    for value <- [
          nil,
          "",
          "https://migration:secret@host/db",
          "postgres://host/db",
          "postgres://migration:secret@host/",
          "postgres://migration:secret@host:0/db",
          "postgres://migration:secret@host/db?username=runtime",
          "postgres://migration:secret@host/db#fragment"
        ] do
      error =
        assert_raise RuntimeError, fn ->
          Release.migration_config!(Repo, fn "DATABASE_DIRECT_URL" -> value end)
        end

      assert error.message ==
               "DATABASE_DIRECT_URL must be a PostgreSQL URL with credentials and no query or fragment"
    end
  end

  test "a running application connection cannot be reused for migration" do
    previous = Application.fetch_env!(:techtree, Repo)
    pid = Process.whereis(Repo)
    assert is_pid(pid)
    System.put_env("DATABASE_DIRECT_URL", "postgres://migration:fixture@127.0.0.1/unused")
    assert_raise RuntimeError, ~r/fresh release eval/, fn -> Release.migrate() end
    assert Process.whereis(Repo) == pid
    assert Application.fetch_env!(:techtree, Repo) == previous
  end

  test "a fresh migration command uses the direct database, reruns harmlessly and restores runtime config" do
    {config, database, name} = disposable_database()

    # If the release falls back to runtime configuration, this user/database cannot connect.
    runtime = Keyword.merge(config, username: "unusable_runtime", database: "unusable_runtime")
    Application.put_env(:techtree, Repo, runtime)

    url =
      direct_database_url(config, name)

    System.put_env("DATABASE_DIRECT_URL", url)

    Release.migrate()
    assert Application.fetch_env!(:techtree, Repo) == runtime
    refute Process.whereis(Repo)
    Release.migrate()
    assert Application.fetch_env!(:techtree, Repo) == runtime

    {:ok, connection} = Postgrex.start_link(database)

    try do
      %{rows: [[^name, count]]} =
        Postgrex.query!(
          connection,
          "SELECT current_database(), count(*) FROM public.schema_migrations",
          []
        )

      assert count > 0
    after
      GenServer.stop(connection)
    end
  end

  test "incomplete imported history stops before changing either ledger" do
    {config, database, name} = disposable_database()

    options =
      Keyword.merge(config,
        default_prefix: "techtree_app",
        migration_default_prefix: "techtree_app"
      )

    Application.put_env(:techtree, Repo, options)

    System.put_env(
      "DATABASE_DIRECT_URL",
      direct_database_url(config, name)
    )

    {:ok, connection} = Postgrex.start_link(database)

    try do
      Postgrex.query!(connection, "CREATE SCHEMA techtree_app", [])

      Postgrex.query!(
        connection,
        "CREATE TABLE public.schema_migrations(version bigint PRIMARY KEY, inserted_at timestamp)",
        []
      )

      Postgrex.query!(connection, "INSERT INTO public.schema_migrations VALUES (1, now())", [])

      Postgrex.query!(
        connection,
        "CREATE TABLE techtree_app.schema_migrations (LIKE public.schema_migrations INCLUDING ALL)",
        []
      )

      assert_raise RuntimeError, ~r/Import the complete Techtree schema/, fn ->
        Release.migrate()
      end

      assert Postgrex.query!(connection, "SELECT version FROM public.schema_migrations", []).rows ==
               [[1]]

      assert Postgrex.query!(connection, "SELECT version FROM techtree_app.schema_migrations", []).rows ==
               []

      assert Application.fetch_env!(:techtree, Repo) == options
      refute Process.whereis(Repo)
    after
      GenServer.stop(connection)
    end
  end

  defp direct_database_url(config, name) do
    username = URI.encode(config[:username], &URI.char_unreserved?/1)
    password = URI.encode(config[:password] || "unused", &URI.char_unreserved?/1)
    "postgresql://#{username}:#{password}@127.0.0.1:#{config[:port] || 5432}/#{name}"
  end

  defp disposable_database do
    config = Repo.config()
    assert config[:hostname] in ["127.0.0.1", "localhost"]
    refute config[:url]
    assert String.starts_with?(config[:database], "techtree_test")
    name = "techtree_release_" <> String.replace(Ecto.UUID.generate(), "-", "")
    database = Keyword.merge(config, database: name, pool: DBConnection.ConnectionPool)
    assert :ok = Ecto.Adapters.Postgres.storage_up(database)

    :ok = Supervisor.terminate_child(Techtree.Supervisor, Repo)

    on_exit(fn ->
      Application.put_env(:techtree, Repo, config)
      {:ok, _} = Supervisor.restart_child(Techtree.Supervisor, Repo)
      Ecto.Adapters.SQL.Sandbox.mode(Repo, :manual)
      :ok = Ecto.Adapters.Postgres.storage_down(database)
    end)

    {config, database, name}
  end
end
