defmodule Techtree.Repo.Migrations.AddLeftMessages do
  @moduledoc """
  Messages left for Techtree's team (`Techtree.Messages.Message`): one new,
  empty table, its check that every message has a sender, its index for reading
  newest first, and one message for each agent's `operation_id`. Nothing
  existing changes. The agents table is in the site's own schema, which is the
  prefix the migration runs with.

  Generated with `mix ash.codegen add_left_messages`.
  """

  use Ecto.Migration

  def up do
    execute("SET LOCAL lock_timeout = '5s'")

    create table(:left_messages, primary_key: false) do
      add :id, :uuid, null: false, default: fragment("gen_random_uuid()"), primary_key: true
      add :topic, :text, null: false
      add :body, :text, null: false
      add :reply_to, :text
      add :sender_name, :text, null: false
      add :operation_id, :uuid

      add :inserted_at, :utc_datetime_usec,
        null: false,
        default: fragment("(now() AT TIME ZONE 'utc')")

      add :human_account_id,
          references(:platform_human_users,
            column: :id,
            name: "left_messages_human_account_id_fkey",
            type: :bigint,
            prefix: "regent_names"
          )

      add :agent_id,
          references(:agents,
            column: :id,
            name: "left_messages_agent_id_fkey",
            type: :uuid,
            prefix: prefix()
          )
    end

    create unique_index(:left_messages, [:agent_id, :operation_id],
             name: "left_messages_unique_agent_operation_index"
           )

    create constraint(:left_messages, :has_sender,
             check: """
               human_account_id IS NOT NULL OR agent_id IS NOT NULL
             """
           )

    create index(:left_messages, [:inserted_at, :id])
  end

  def down do
    drop_if_exists index(:left_messages, [:inserted_at, :id])

    drop_if_exists constraint(:left_messages, :has_sender)

    drop constraint(:left_messages, "left_messages_agent_id_fkey")

    drop constraint(:left_messages, "left_messages_human_account_id_fkey")

    drop_if_exists unique_index(:left_messages, [:agent_id, :operation_id],
                     name: "left_messages_unique_agent_operation_index"
                   )

    drop table(:left_messages)
  end
end
