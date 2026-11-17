defmodule Techtree.Repo.Migrations.AddJobOrders do
  @moduledoc """
  Job orders and their payments (`Techtree.Jobs.Order`, `Techtree.Jobs.Deposit`):
  two new, empty tables in the site's own schema. An order references the agent
  that asked, in the same schema, and its person's account in the table Regents
  owns; it checks that a quote is set whole or not at all, and keeps each
  payment reference once. A deposit references its order and is kept once per
  transaction and log. Nothing existing changes. The agents table is in the
  site's own schema, which is the prefix the migration runs with.

  Generated with `mix ash.codegen add_job_orders`.
  """

  use Ecto.Migration

  def up do
    execute("SET LOCAL lock_timeout = '5s'")

    create table(:job_orders, primary_key: false) do
      add :id, :uuid, null: false, default: fragment("gen_random_uuid()"), primary_key: true
      add :lane, :text, null: false
      add :title, :text, null: false
      add :success, :text, null: false
      add :quote_amount, :bigint
      add :quote_scope, :text
      add :quote_expires_at, :utc_datetime_usec
      add :payment_reference, :text
      add :next_block, :bigint

      add :requested_at, :utc_datetime_usec,
        null: false,
        default: fragment("(now() AT TIME ZONE 'utc')")

      add :checking_at, :utc_datetime_usec
      add :quoted_at, :utc_datetime_usec
      add :paid_at, :utc_datetime_usec
      add :refused_at, :utc_datetime_usec
      add :expired_at, :utc_datetime_usec
      add :cancelled_at, :utc_datetime_usec
      add :state, :text, null: false, default: "requested"

      add :agent_id,
          references(:agents,
            column: :id,
            name: "job_orders_agent_id_fkey",
            type: :uuid,
            prefix: prefix()
          ),
          null: false

      add :human_account_id,
          references(:platform_human_users,
            column: :id,
            name: "job_orders_human_account_id_fkey",
            type: :bigint,
            prefix: "regent_names"
          )
    end

    create unique_index(:job_orders, [:payment_reference],
             name: "job_orders_unique_payment_reference_index"
           )

    create constraint(:job_orders, :quote_whole,
             check: """
               num_nulls(quote_amount, quote_scope, quote_expires_at, payment_reference, next_block) = 5 OR (num_nulls(quote_amount, quote_scope, quote_expires_at, payment_reference, next_block) = 0 AND quote_amount > 0)
             """
           )

    create table(:job_deposits, primary_key: false) do
      add :id, :uuid, null: false, default: fragment("gen_random_uuid()"), primary_key: true
      add :transaction_hash, :text, null: false
      add :log_index, :bigint, null: false
      add :depositor, :text, null: false
      add :amount, :decimal, null: false
      add :block_number, :bigint, null: false

      add :recorded_at, :utc_datetime_usec,
        null: false,
        default: fragment("(now() AT TIME ZONE 'utc')")

      add :order_id,
          references(:job_orders,
            column: :id,
            name: "job_deposits_order_id_fkey",
            type: :uuid,
            prefix: prefix()
          ),
          null: false
    end

    create unique_index(:job_deposits, [:transaction_hash, :log_index],
             name: "job_deposits_unique_log_index"
           )

    create index(:job_deposits, [:order_id])
  end

  def down do
    drop table(:job_deposits)
    drop table(:job_orders)
  end
end
