defmodule Techtree.Release do
  @moduledoc """
  What a deployed release is asked to do without Mix, and where its own
  artifacts live.

  Migrating, importing the catalog, and moving the pointer that selects the
  published installation contract are separate commands on purpose: booting the
  application never imports and never republishes anything (spec section 8.10),
  so a release that starts is a release serving exactly what it was serving
  before.
  """

  alias Techtree.Catalog.Error
  alias Techtree.Catalog.Publication

  @app :techtree
  # Earlier migrations contain public-qualified references. They are imported,
  # together with their ledger, before this application selects techtree_app.
  @imported_through 20_260_828_235_308

  @default_starter_skill_root {:priv, "release"}
  @platform_schema "regent_names"

  @table_exists """
  SELECT EXISTS (
    SELECT 1 FROM pg_catalog.pg_class AS c
    JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
    WHERE n.nspname = $1 AND c.relname = $2 AND c.relkind IN ('r', 'p')
  )
  """
  @schema_exists "SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_namespace WHERE nspname = $1)"

  @doc """
  Run every pending migration, through the release login bin/migrate selects.
  """
  @spec migrate() :: :ok
  def migrate do
    load_app()

    for repo <- repos() do
      {:ok, _result, _apps} =
        Ecto.Migrator.with_repo(repo, fn repo ->
          require_imported_history!(repo)
          require_signed_access_schema!(repo)
          Ecto.Migrator.run(repo, :up, all: true, prefix: repo.default_prefix())
        end)
    end

    :ok
  end

  @doc "Read-only shared-schema prerequisites. This site never applies shared migrations."
  def require_signed_access_schema!(repo) do
    :ok = require_shared_migrations!(repo)
    :ok = RegentAgents.Migrator.require_pairing_history!(repo)
    RegentCredits.Migrator.require_pairing_grants!(repo)
  end

  # The Agents, Credits and Points code this release carries reads tables and columns
  # from every migration its pinned library ships, so each must already be in
  # that schema's own ledger. Every missing version is named at once.
  defp require_shared_migrations!(repo) do
    case unapplied_shared_migrations(repo) do
      [] ->
        :ok

      unapplied ->
        raise "These separately approved shared migrations must be applied before deployment: " <>
                Enum.join(unapplied, ", ")
    end
  end

  defp unapplied_shared_migrations(repo) do
    for {app, schema} <- [
          regent_agents: "regent_agents",
          regent_credits: "regent_credits",
          regent_points: "regent_points"
        ],
        {:down, version, _name} <-
          Ecto.Migrator.migrations(repo, [Application.app_dir(app, "priv/repo/migrations")],
            prefix: schema,
            skip_table_creation: true,
            migration_lock: false
          ),
        do: "#{schema} #{version}"
  end

  @doc """
  Prepares an empty staging database for the first deployment: creates a
  staging-only copy of the tables this repository reads but does not own
  (`regent_names.platform_human_users`), in the test suite's shape, runs every
  migration of this repository, then creates the shared agent, Credits, Points
  and identity tables, which Regents migrates in production. It refuses a
  database that already carries migration state or the regent_names schema and
  repairs nothing: recovery from a half-finished bootstrap is to destroy and
  recreate the staging database.
  """
  @spec bootstrap_staging() :: :ok
  def bootstrap_staging do
    # Read before anything opens a connection, so no configuration mistake can
    # point this command at a database outside staging.
    if System.get_env("TECHTREE_DEPLOYMENT_ROLE") != "staging",
      do: raise("bootstrap-staging requires TECHTREE_DEPLOYMENT_ROLE to be exactly staging")

    load_app()

    for repo <- repos() do
      {:ok, _result, _apps} =
        Ecto.Migrator.with_repo(repo, fn repo ->
          refuse_existing_state!(repo)
          # The fixture is the only definition of these tables' shape in the repository.
          Techtree.LocalDatabaseFixture.create_shared_tables!()
          Ecto.Migrator.run(repo, :up, all: true, prefix: repo.default_prefix())
          RegentAgents.Migrator.up(repo)
          RegentCredits.Migrator.up(repo)
          RegentPoints.Migrator.up(repo)
          RegentIdentity.Migrator.up(repo)
        end)
    end

    :ok
  end

  @doc """
  Import and activate the immutable catalog snapshot for a full source revision.
  """
  @spec import_catalog(String.t()) :: :ok
  def import_catalog(revision) do
    load_app()

    {:ok, _apps} = Application.ensure_all_started(@app)

    path =
      case Techtree.Catalog.snapshot_path(revision) do
        {:ok, path} -> path
        {:error, error} -> raise error
      end

    release = Techtree.Catalog.Importer.import!(path)

    IO.puts("imported catalog #{release.catalog_digest} on channel #{release.channel}")
    :ok
  end

  @doc """
  Publish one already-staged bootstrap release on its channel.

  This is the rollback command: releases are immutable, and which one a channel
  publishes is a pointer. Moving it forward and moving it back are the same
  operation, and neither deletes, rewrites, or reaches anything a participant
  holds locally.
  """
  @spec publish_bootstrap(String.t(), String.t() | nil) :: :ok
  def publish_bootstrap(digest, channel \\ nil) do
    load_app()

    {:ok, _apps} = Application.ensure_all_started(@app)

    case Publication.publish(digest, channel: channel) do
      {:ok, switch} ->
        IO.puts("""
        channel #{switch.channel}
        published #{switch.published}
        previously #{switch.previous || "nothing"}\
        """)

        :ok

      {:error, %Error{} = error} ->
        IO.puts(:stderr, Error.summary(error))
        exit({:shutdown, 1})
    end
  end

  @doc """
  Every bootstrap release a channel has staged, newest first, marking the one it
  publishes now.
  """
  @spec list_bootstrap_releases(String.t() | nil) :: :ok
  def list_bootstrap_releases(channel \\ nil) do
    load_app()

    {:ok, _apps} = Application.ensure_all_started(@app)

    [channel: channel]
    |> Publication.list()
    |> Enum.each(fn release ->
      IO.puts(
        "#{marker(release)} #{release.payload_digest} #{release.published_at} " <>
          "cli #{release.cli_version} plugin #{release.plugin_revision}"
      )
    end)
  end

  @doc """
  The directory holding the release artifacts this build serves beside the
  catalog bundle — today, the starter Skills.

  Configured the same way as the catalog root: `{:priv, subdirectory}` names a
  directory shipped inside the release, a plain path names one deployed beside
  it.
  """
  @spec starter_skill_root() :: Path.t()
  def starter_skill_root do
    @app
    |> Application.get_env(__MODULE__, [])
    |> Keyword.get(:starter_skill_root, @default_starter_skill_root)
    |> case do
      {:priv, subdirectory} -> Application.app_dir(@app, ["priv", subdirectory])
      path when is_binary(path) -> path
    end
  end

  defp marker(%{active: true}), do: "*"
  defp marker(%{active: false}), do: " "

  defp repos do
    Application.fetch_env!(@app, :ecto_repos)
  end

  defp require_imported_history!(repo) do
    if repo.default_prefix() != "public" do
      migrations =
        Ecto.Migrator.migrations(repo, Ecto.Migrator.migrations_path(repo),
          prefix: repo.default_prefix(),
          skip_table_creation: true
        )

      incomplete? =
        Enum.any?(migrations, fn {status, version, _name} ->
          status == :down and version <= @imported_through
        end)

      if incomplete? do
        raise "Import the complete Techtree schema and migration history before migrating"
      end
    end
  end

  defp refuse_existing_state!(repo) do
    prefix = repo.default_prefix()
    source = repo.config()[:migration_source] || "schema_migrations"

    if table_exists?(repo, prefix, source) do
      raise "#{prefix}.#{source} already exists: destroy and recreate the staging database"
    end

    if schema_exists?(repo, @platform_schema) do
      raise "#{@platform_schema} schema already exists: destroy and recreate the staging database"
    end
  end

  defp table_exists?(repo, prefix, table) do
    %{rows: [[exists?]]} = Ecto.Adapters.SQL.query!(repo, @table_exists, [prefix, table])
    exists?
  end

  defp schema_exists?(repo, schema) do
    %{rows: [[exists?]]} = Ecto.Adapters.SQL.query!(repo, @schema_exists, [schema])
    exists?
  end

  defp load_app do
    Application.load(@app)
  end
end
