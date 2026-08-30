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

  @default_starter_skill_root {:priv, "release"}

  @doc """
  Run every pending migration.
  """
  @spec migrate() :: :ok
  def migrate do
    load_app()

    for repo <- repos() do
      {:ok, _result, _apps} =
        Ecto.Migrator.with_repo(repo, &Ecto.Migrator.run(&1, :up, all: true))
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

  defp repos do
    Application.fetch_env!(@app, :ecto_repos)
  end

  defp load_app do
    Application.load(@app)
  end
end
