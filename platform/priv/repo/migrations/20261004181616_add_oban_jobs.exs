defmodule Techtree.Repo.Migrations.AddObanJobs do
  @moduledoc """
  Background jobs, in this site's own schema: the repo's, which a release also
  migrates with. `prefix()` holds it only when the runner was given one.
  """

  use Ecto.Migration

  def up, do: Oban.Migrations.up(prefix: Techtree.Repo.default_prefix())

  def down, do: Oban.Migrations.down(prefix: Techtree.Repo.default_prefix(), version: 1)
end
