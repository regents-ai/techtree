defmodule Techtree.ReleaseMigrationTest do
  use ExUnit.Case, async: false

  alias Techtree.{Release, Repo}

  test "incomplete imported history stops before changing either ledger" do
    database = disposable_database()

    options =
      Keyword.merge(database,
        default_prefix: "techtree_app",
        migration_default_prefix: "techtree_app"
      )

    Application.put_env(:techtree, Repo, options)

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

    database
  end
end
