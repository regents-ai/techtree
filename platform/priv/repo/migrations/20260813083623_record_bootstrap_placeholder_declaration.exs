defmodule Techtree.Repo.Migrations.RecordBootstrapPlaceholderDeclaration do
  @moduledoc """
  Require every bootstrap release to declare whether its pinned coordinates are
  placeholders.

  The declaration cannot be guessed for rows that predate it: reading a
  placeholder release as a real one would publish an installation path that
  installs nothing. Rows imported before this column existed therefore do not
  survive it — every one of them is derived from a catalog bundle and is
  reproduced exactly by importing that bundle again:

      mix catalog.import --path priv/catalog

  Until that runs, the application reports no active release, which is the
  truth.
  """

  use Ecto.Migration

  def up do
    execute "DELETE FROM catalog_entries"
    execute "DELETE FROM catalog_releases"
    execute "DELETE FROM bootstrap_releases"

    alter table(:bootstrap_releases) do
      add :placeholder_release, :boolean, null: false
    end
  end

  def down do
    alter table(:bootstrap_releases) do
      remove :placeholder_release
    end
  end
end
