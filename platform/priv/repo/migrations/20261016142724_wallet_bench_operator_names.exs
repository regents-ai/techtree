defmodule Techtree.Repo.Migrations.WalletBenchOperatorNames do
  @moduledoc """
  The Wallet Bench records which operator ran an operator action (Sean's named
  go, 16 October 2026): machine and attempt events gain `operator`, payments
  `settled_by`, and version notes `added_by`. Each column is new and nullable;
  existing rows keep no name, and jobs record none. Down drops only these.
  """

  use Ecto.Migration

  def up do
    alter table(:wallet_bench_attempt_events) do
      add :operator, :text
    end

    alter table(:wallet_bench_machine_events) do
      add :operator, :text
    end

    alter table(:wallet_bench_payments) do
      add :settled_by, :text
    end

    alter table(:wallet_bench_version_notes) do
      add :added_by, :text
    end
  end

  def down do
    alter table(:wallet_bench_version_notes) do
      remove :added_by
    end

    alter table(:wallet_bench_payments) do
      remove :settled_by
    end

    alter table(:wallet_bench_machine_events) do
      remove :operator
    end

    alter table(:wallet_bench_attempt_events) do
      remove :operator
    end
  end
end
