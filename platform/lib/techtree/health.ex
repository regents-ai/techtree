defmodule Techtree.Health do
  @moduledoc "Whether every migration this release carries is applied, for the health answer."

  alias Techtree.Repo

  @doc """
  True when every migration file this release carries is recorded in the site's
  own schema. It only reads: no lock, and it never creates the ledger. A
  database that does not answer is `false`.
  """
  @spec migrations_applied?() :: boolean()
  def migrations_applied? do
    Repo
    |> Ecto.Migrator.migrations([Application.app_dir(:techtree, "priv/repo/migrations")],
      prefix: Repo.default_prefix(),
      skip_table_creation: true,
      migration_lock: false,
      timeout: 1_000,
      log: false
    )
    |> Enum.all?(&match?({:up, _version, _name}, &1))
  rescue
    _error -> false
  catch
    :exit, _reason -> false
  end
end
