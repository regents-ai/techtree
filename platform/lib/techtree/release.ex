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

  @doc """
  Run every pending migration.
  """
  @spec migrate() :: :ok
  def migrate do
    load_app()

    for repo <- repos() do
      {:ok, _result, _apps} =
        with_migration_repo(repo, fn repo ->
          require_imported_history!(repo)
          Ecto.Migrator.run(repo, :up, all: true, prefix: repo.default_prefix())
        end)
    end

    :ok
  end

  @doc """
  Import and activate a catalog bundle, defaulting to the one this release ships.
  """
  @spec import_catalog(Path.t() | nil) :: :ok
  def import_catalog(path \\ nil) do
    load_app()

    {:ok, _apps} = Application.ensure_all_started(@app)

    release = Techtree.Catalog.Importer.import!(path || Techtree.Catalog.catalog_root())

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
  catalog bundle — today, the starter Skill.

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

  @doc """
  Select the explicitly supplied migration connection, retaining schema and transport settings.
  Release commands never fall back to the application's runtime credentials.
  """
  def migration_config!(repo, getenv \\ &System.get_env/1) do
    url = getenv.("DATABASE_DIRECT_URL")

    connection =
      try do
        %URI{scheme: scheme, host: host, userinfo: userinfo, query: query, fragment: nil} =
          URI.new!(url || "")

        true = scheme in ["postgres", "postgresql"] and is_binary(host) and host != ""
        true = query in [nil, ""]
        [username, password] = String.split(userinfo || "", ":", parts: 2)
        true = String.trim(username) != "" and String.trim(password) != ""
        parsed = Ecto.Repo.Supervisor.parse_url(url) |> Keyword.put_new(:port, 5432)
        true = Keyword.get(parsed, :port, 5432) in 1..65_535
        true = String.trim(Keyword.fetch!(parsed, :database)) != ""
        parsed
      rescue
        _error -> :invalid_url
      end

    if connection == :invalid_url do
      raise "DATABASE_DIRECT_URL must be a PostgreSQL URL with credentials and no query or fragment"
    end

    @app
    |> Application.fetch_env!(repo)
    |> Keyword.drop([
      :url,
      :hostname,
      :port,
      :socket,
      :socket_dir,
      :endpoints,
      :username,
      :password,
      :database
    ])
    |> Keyword.merge(connection)
  end

  # with_repo reuses a running Repo. Changing its configuration would not change
  # those existing credentials, so migration commands require a fresh release eval.
  defp with_migration_repo(repo, fun) do
    if Process.whereis(repo) do
      raise "Migration requires a fresh release eval; the application Repo is already running"
    end

    previous = Application.fetch_env!(@app, repo)
    Application.put_env(@app, repo, migration_config!(repo))

    try do
      Ecto.Migrator.with_repo(repo, fun)
    after
      Application.put_env(@app, repo, previous)
    end
  end

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

  defp load_app do
    Application.load(@app)
  end
end
