defmodule Techtree.Repo.Migrations.AddAgents do
  @moduledoc """
  Adds `agents`, the record of each wallet that signs requests here
  (`Techtree.Agents.Agent`), as ash-template keeps it. The table starts empty;
  each agent's first signed request adds its row. Down drops it again.
  """

  use Ecto.Migration

  def up do
    create table(:agents, primary_key: false) do
      add :id, :uuid, null: false, default: fragment("gen_random_uuid()"), primary_key: true
      add :wallet_address, :text, null: false
      add :world_id_human_id, :text
      add :world_id_agent_count, :bigint
      add :last_seen_at, :utc_datetime_usec, null: false, default: fragment("now()")

      add :inserted_at, :utc_datetime_usec,
        null: false,
        default: fragment("(now() AT TIME ZONE 'utc')")
    end

    create unique_index(:agents, [:wallet_address], name: "agents_unique_wallet_address_index")

    create constraint(:agents, :world_id_whole,
             check: """
               (world_id_human_id IS NULL) = (world_id_agent_count IS NULL)
             """
           )
  end

  def down do
    drop_if_exists constraint(:agents, :world_id_whole)

    drop_if_exists unique_index(:agents, [:wallet_address],
                     name: "agents_unique_wallet_address_index"
                   )

    drop table(:agents)
  end
end
