defmodule Techtree.Repo.Migrations.AddEnquiries do
  @moduledoc """
  Enquiries visitors send from the contact form (`Techtree.Messages.Enquiry`):
  one new, empty table and its index for reading newest first, in the site's own
  schema. Nothing existing changes.

  Generated with `mix ash.codegen add_enquiries`.
  """

  use Ecto.Migration

  def up do
    execute("SET LOCAL lock_timeout = '5s'")

    create table(:enquiries, primary_key: false) do
      add :id, :uuid, null: false, default: fragment("gen_random_uuid()"), primary_key: true
      add :name, :text, null: false
      add :email, :text, null: false
      add :company, :text, null: false
      add :service, :text, null: false
      add :goal, :text, null: false

      add :inserted_at, :utc_datetime_usec,
        null: false,
        default: fragment("(now() AT TIME ZONE 'utc')")
    end

    create index(:enquiries, [:inserted_at, :id])
  end

  def down do
    drop_if_exists index(:enquiries, [:inserted_at, :id])

    drop table(:enquiries)
  end
end
