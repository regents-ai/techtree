defmodule Techtree.Repo.Migrations.ReshapeThePublicRunLog do
  @moduledoc """
  The run log takes the shape the founder ruled on: publication entries,
  publication events, and a contributor address that is three columns and no
  associations.

  Nothing has been released, so the three tables the previous migration created
  are dropped rather than migrated. What replaces them is not the same shape
  under new names — an entry now carries its own log sequence, its acceptance
  time and the receipt this site issued, all written in one insert; an event is
  the append-only record of acceptance and withdrawal carrying the
  participant's own signature; and a contributor address is keyed by the
  participant's key rather than by an entry, so nothing can render one by
  following an association.

  Three unique indexes carry the idempotence rules. One bundle is published
  once, one log sequence is held by one entry, and one participant publishes
  one run once.
  """

  use Ecto.Migration

  def up do
    drop constraint(
           :network_contributor_addresses,
           "network_contributor_addresses_submission_id_fkey"
         )

    drop table(:network_contributor_addresses)

    drop constraint(:network_withdrawals, "network_withdrawals_submission_id_fkey")

    drop table(:network_withdrawals)
    drop table(:network_submissions)

    execute("DROP SEQUENCE network_submission_sequence")

    create table(:network_publication_entries, primary_key: false) do
      add :id, :uuid, null: false, default: fragment("gen_random_uuid()"), primary_key: true
      add :log_sequence, :bigint, null: false
      add :accepted_at, :utc_datetime_usec, null: false
      add :bundle_digest, :text, null: false
      add :submission_bytes, :binary, null: false
      add :submission_digest, :text, null: false
      add :run_id, :text, null: false
      add :campaign_spec_digest, :text, null: false
      add :data_policy_digest, :text, null: false
      add :climb_reference, :text, null: false
      add :participant_kind, :text, null: false
      add :participant_key_id, :text, null: false
      add :participant_public_key, :text, null: false
      add :subject_provider, :text, null: false
      add :subject_model, :text, null: false
      add :subject_harness, :text, null: false
      add :subject_harness_version, :text, null: false
      add :baseline_mean, :float, null: false
      add :candidate_mean, :float, null: false
      add :absolute_delta, :float, null: false
      add :wins, :bigint, null: false
      add :losses, :bigint, null: false
      add :ties, :bigint, null: false
      add :task_count, :bigint, null: false
      add :statuses, :map, null: false, default: %{}
      add :decision, :text, null: false
      add :proof_grade, :text, null: false
      add :verification_checks_run, :bigint, null: false
      add :verification_checks_passed, :bigint, null: false
      add :task_deltas, {:array, :map}, null: false, default: []
      add :receipt_bytes, :binary, null: false
      add :receipt_digest, :text, null: false
      add :network_key_id, :text, null: false
      add :withdrawn_at, :utc_datetime_usec
    end

    create unique_index(:network_publication_entries, [:bundle_digest],
             name: "network_publication_entries_unique_bundle_digest_index"
           )

    create unique_index(:network_publication_entries, [:log_sequence],
             name: "network_publication_entries_unique_log_sequence_index"
           )

    create unique_index(:network_publication_entries, [:participant_key_id, :run_id],
             name: "network_publication_entries_unique_participant_run_index"
           )

    create table(:network_publication_events, primary_key: false) do
      add :id, :uuid, null: false, default: fragment("gen_random_uuid()"), primary_key: true
      add :kind, :text, null: false
      add :payload_digest, :text, null: false
      add :participant_signature, :text, null: false

      add :inserted_at, :utc_datetime_usec,
        null: false,
        default: fragment("(now() AT TIME ZONE 'utc')")

      add :publication_entry_id,
          references(:network_publication_entries,
            column: :id,
            name: "network_publication_events_publication_entry_id_fkey",
            type: :uuid,
            prefix: "public",
            on_delete: :nothing,
            on_update: :nothing
          ),
          null: false
    end

    create table(:network_contributor_addresses, primary_key: false) do
      add :id, :uuid, null: false, default: fragment("gen_random_uuid()"), primary_key: true
      add :participant_key_id, :text, null: false
      add :contributor_address_unverified, :text, null: false

      add :inserted_at, :utc_datetime_usec,
        null: false,
        default: fragment("(now() AT TIME ZONE 'utc')")
    end

    execute("CREATE SEQUENCE network_publication_sequence")
  end

  def down do
    execute("DROP SEQUENCE network_publication_sequence")

    drop table(:network_contributor_addresses)

    drop constraint(
           :network_publication_events,
           "network_publication_events_publication_entry_id_fkey"
         )

    drop table(:network_publication_events)

    drop_if_exists unique_index(:network_publication_entries, [:participant_key_id, :run_id],
                     name: "network_publication_entries_unique_participant_run_index"
                   )

    drop_if_exists unique_index(:network_publication_entries, [:log_sequence],
                     name: "network_publication_entries_unique_log_sequence_index"
                   )

    drop_if_exists unique_index(:network_publication_entries, [:bundle_digest],
                     name: "network_publication_entries_unique_bundle_digest_index"
                   )

    drop table(:network_publication_entries)

    # What the previous migration created, put back so that rolling back past
    # this one has something to drop. It comes back empty: the rows that were
    # in it were dropped when this migration ran, and a migration cannot
    # invent evidence it destroyed.
    create table(:network_submissions, primary_key: false) do
      add :id, :uuid, null: false, default: fragment("gen_random_uuid()"), primary_key: true
      add :sequence, :bigint, null: false
      add :bundle_digest, :text, null: false
      add :run_id, :text, null: false
      add :campaign_spec_digest, :text, null: false
      add :data_policy_digest, :text, null: false
      add :climb_reference, :text, null: false
      add :executor_kind, :text, null: false
      add :executor_key_id, :text, null: false
      add :executor_public_key, :text, null: false
      add :subject_model, :text, null: false
      add :subject_harness, :text, null: false
      add :subject_harness_version, :text, null: false
      add :baseline_mean, :float, null: false
      add :candidate_mean, :float, null: false
      add :absolute_delta, :float, null: false
      add :wins, :bigint, null: false
      add :losses, :bigint, null: false
      add :ties, :bigint, null: false
      add :task_count, :bigint, null: false
      add :decision, :text, null: false
      add :proof_grade, :text, null: false
      add :verification_checks_run, :bigint, null: false
      add :verification_checks_passed, :bigint, null: false
      add :task_deltas, {:array, :map}, null: false, default: []
      add :raw_payload, :binary, null: false
      add :withdrawn_at, :utc_datetime_usec

      add :inserted_at, :utc_datetime_usec,
        null: false,
        default: fragment("(now() AT TIME ZONE 'utc')")

      add :updated_at, :utc_datetime_usec,
        null: false,
        default: fragment("(now() AT TIME ZONE 'utc')")
    end

    create unique_index(:network_submissions, [:bundle_digest],
             name: "network_submissions_unique_bundle_digest_index"
           )

    create unique_index(:network_submissions, [:sequence],
             name: "network_submissions_unique_sequence_index"
           )

    create table(:network_withdrawals, primary_key: false) do
      add :id, :uuid, null: false, default: fragment("gen_random_uuid()"), primary_key: true
      add :reason, :text, null: false

      add :inserted_at, :utc_datetime_usec,
        null: false,
        default: fragment("(now() AT TIME ZONE 'utc')")

      add :submission_id,
          references(:network_submissions,
            column: :id,
            name: "network_withdrawals_submission_id_fkey",
            type: :uuid,
            prefix: "public",
            on_delete: :nothing,
            on_update: :nothing
          ),
          null: false
    end

    create table(:network_contributor_addresses, primary_key: false) do
      add :address, :text, null: false, primary_key: true
      add :submission_count, :bigint, null: false, default: 1
      add :first_seen_at, :utc_datetime_usec, null: false
      add :last_seen_at, :utc_datetime_usec, null: false

      add :submission_id,
          references(:network_submissions,
            column: :id,
            name: "network_contributor_addresses_submission_id_fkey",
            type: :uuid,
            prefix: "public",
            on_delete: :nothing,
            on_update: :nothing
          ),
          null: false
    end

    execute("CREATE SEQUENCE network_submission_sequence")
  end
end
