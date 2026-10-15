defmodule Mix.Tasks.Techtree.SetupLocalAuth do
  @moduledoc """
  Creates the local copy of `regent_names.platform_human_users`, which Regents
  owns in production and the account migration references, before a dev or
  test database is migrated. `mix setup` and `mix test` run it between creating
  the database and migrating it.
  """
  use Mix.Task

  @shortdoc "Prepares the shared account table a local Techtree database references"

  @impl true
  def run(_args) do
    unless Mix.env() in [:dev, :test], do: Mix.raise("local database setup is dev and test only")
    Mix.Task.run("app.config")

    {:ok, _, _} =
      Ecto.Migrator.with_repo(Techtree.Repo, fn _repo ->
        Techtree.LocalDatabaseFixture.create_shared_tables!()
      end)

    Mix.shell().info("Local Techtree database is ready.")
  end
end
