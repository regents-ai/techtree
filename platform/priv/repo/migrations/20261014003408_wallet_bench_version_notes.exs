defmodule Techtree.Repo.Migrations.WalletBenchVersionNotes do
  @moduledoc """
  Extra notes by release (Sean, 14 October 2026: "for all tests, include a
  'extra notes' or strange things for each harness or each wallet-signer, like
  an addendum, based on version number").

  `wallet_bench_version_notes` holds one row per note: an agent or a wallet
  tool, the release as the bench's results show it, the note in plain words and
  the run that showed it, when one did.

  `wallet_bench_extra_notes` is the view Patchbay reads, beside the other
  `wallet_bench_*` views: `kind` and `id` as `wallet_bench_roster` has them,
  `version` as `wallet_bench_pair_summary` shows `harness_version` and
  `wallet_version`, the note, the run's page and when it was written. A note
  sits beside every result of that release. No result reads one.
  """

  use Ecto.Migration

  def up do
    create table(:wallet_bench_version_notes, primary_key: false) do
      add :id, :uuid, null: false, default: fragment("gen_random_uuid()"), primary_key: true
      add :kind, :text, null: false
      add :subject_id, :text, null: false
      add :version, :text, null: false
      add :text, :text, null: false

      add :inserted_at, :utc_datetime_usec,
        null: false,
        default: fragment("(now() AT TIME ZONE 'utc')")

      add :attempt_id,
          references(:wallet_bench_attempts,
            column: :id,
            name: "wallet_bench_version_notes_attempt_id_fkey",
            type: :uuid,
            on_delete: :nothing,
            on_update: :nothing
          )
    end

    s = Techtree.Repo.default_prefix()

    execute("""
    CREATE VIEW #{s}.wallet_bench_extra_notes AS
    SELECT n.kind, n.subject_id AS id, n.version, n.text AS note,
           'https://techtree.sh/wallet-bench/' || n.attempt_id AS run_url,
           n.inserted_at AS noted_at
    FROM #{s}.wallet_bench_version_notes n
    """)
  end

  def down do
    execute("DROP VIEW #{Techtree.Repo.default_prefix()}.wallet_bench_extra_notes")

    drop constraint(:wallet_bench_version_notes, "wallet_bench_version_notes_attempt_id_fkey")

    drop table(:wallet_bench_version_notes)
  end
end
