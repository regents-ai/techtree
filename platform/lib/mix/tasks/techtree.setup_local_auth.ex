defmodule Mix.Tasks.Techtree.SetupLocalAuth do
  @moduledoc """
  Creates the local copy of `regent_names.platform_human_users`, which Regents
  owns in production and the account migration references, then the shared
  agent pairing and profile tables from regent_agents' and regent_identity's own
  migrations, which Regents alone runs in production. `mix setup` and `mix test`
  run it between creating a dev or test database and migrating it. Running it
  again changes nothing.
  """
  use Mix.Task

  @shortdoc "Prepares the shared account table a local Techtree database references"

  @impl true
  def run(_args) do
    unless Mix.env() in [:dev, :test], do: Mix.raise("local database setup is dev and test only")
    Mix.Task.run("app.config")

    {:ok, _, _} =
      Ecto.Migrator.with_repo(Techtree.Repo, fn repo ->
        Techtree.LocalDatabaseFixture.create_shared_tables!()
        RegentAgents.Migrator.up(repo)
        RegentIdentity.Migrator.up(repo)
      end)

    Mix.shell().info("Local Techtree database is ready.")
  end
end
