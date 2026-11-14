defmodule Techtree.Repo.Migrations.AddProjects do
  @moduledoc """
  Projects the team delivers to customers (`Techtree.Projects.Project`): one
  new, empty table in the site's own schema, with its references to the
  customer's and the admins' accounts in the table Regents owns, its check that
  a standing project keeps its contents and a withdrawn one keeps none, one
  standing delivery of each package to each customer, and its index for the
  team's newest-first list. Nothing existing changes.

  Generated with `mix ash.codegen add_projects`.
  """

  use Ecto.Migration

  def up do
    execute("SET LOCAL lock_timeout = '5s'")

    create table(:projects, primary_key: false) do
      add :id, :uuid, null: false, default: fragment("gen_random_uuid()"), primary_key: true
      add :title, :text, null: false
      add :line, :text, null: false
      add :verdict, :text, null: false
      add :manifest, :map
      add :report_md, :text
      add :package, :binary
      add :package_sha256, :text, null: false
      add :package_size, :bigint, null: false
      add :customer_name, :text, null: false

      add :delivered_at, :utc_datetime_usec,
        null: false,
        default: fragment("(now() AT TIME ZONE 'utc')")

      add :delivered_by_name, :text, null: false
      add :withdrawn_at, :utc_datetime_usec
      add :withdrawn_by_name, :text

      add :human_account_id,
          references(:platform_human_users,
            column: :id,
            name: "projects_human_account_id_fkey",
            type: :bigint,
            prefix: "regent_names"
          ),
          null: false

      add :delivered_by_id,
          references(:platform_human_users,
            column: :id,
            name: "projects_delivered_by_id_fkey",
            type: :bigint,
            prefix: "regent_names"
          ),
          null: false

      add :withdrawn_by_id,
          references(:platform_human_users,
            column: :id,
            name: "projects_withdrawn_by_id_fkey",
            type: :bigint,
            prefix: "regent_names"
          )
    end

    create unique_index(:projects, [:human_account_id, :package_sha256],
             name: "projects_unique_standing_package_index",
             where: "(withdrawn_at IS NULL)"
           )

    create constraint(:projects, :contents_until_withdrawn,
             check: """
               (withdrawn_at IS NULL) = (package IS NOT NULL AND manifest IS NOT NULL AND report_md IS NOT NULL)
             """
           )

    create index(:projects, [:delivered_at, :id])
  end

  def down do
    drop_if_exists index(:projects, [:delivered_at, :id])

    drop_if_exists constraint(:projects, :contents_until_withdrawn)

    drop constraint(:projects, "projects_withdrawn_by_id_fkey")

    drop constraint(:projects, "projects_delivered_by_id_fkey")

    drop constraint(:projects, "projects_human_account_id_fkey")

    drop_if_exists unique_index(:projects, [:human_account_id, :package_sha256],
                     name: "projects_unique_standing_package_index"
                   )

    drop table(:projects)
  end
end
