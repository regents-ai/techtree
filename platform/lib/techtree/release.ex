defmodule Techtree.Release do
  @moduledoc """
  The two things a deployed release is asked to do without Mix.

  Migrating and importing the catalog are separate commands on purpose: booting
  the application never imports anything (spec section 8.10), so a release that
  starts is a release serving exactly the catalog it was serving before.
  """

  @app :techtree

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

  defp repos do
    Application.fetch_env!(@app, :ecto_repos)
  end

  defp load_app do
    Application.load(@app)
  end
end
