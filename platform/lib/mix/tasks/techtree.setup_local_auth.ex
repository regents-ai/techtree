defmodule Mix.Tasks.Techtree.SetupLocalAuth do
  use Mix.Task

  @shortdoc "Prepares the shared account table a local Techtree database references"

  # The account migration references regent_names.platform_human_users, which
  # Regents owns in production. A local database gets the fixture's copy before
  # its migrations run; `mix setup` and `mix test` run this between creating the
  # database and migrating it.
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
