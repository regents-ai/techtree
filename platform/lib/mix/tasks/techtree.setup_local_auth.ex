defmodule Mix.Tasks.Techtree.SetupLocalAuth do
  @moduledoc """
  Prepares a local dev database the way staging's first deployment is
  prepared (`Techtree.Release.prepare_database!/2`): the tables this repository
  reads but does not own (`regent_names.platform_human_users`, which Regents
  owns in production), every shared change this site carries, then Techtree's
  own migrations. `mix setup` runs it. Running it again changes nothing.
  """
  use Mix.Task

  @shortdoc "Prepares the guarded local Techtree database"

  # Only the database connection runs, so a database without the job tables yet
  # can still be brought up to date.
  @impl true
  def run(_args) do
    unless Mix.env() == :dev, do: Mix.raise("local database setup is dev only")
    Mix.Task.run("app.config")

    {:ok, _, _} =
      Ecto.Migrator.with_repo(Techtree.Repo, fn _repo ->
        Techtree.LocalDatabaseFixture.ensure_human_accounts!()
      end)

    Mix.shell().info("Local Techtree database is ready.")
  end
end
