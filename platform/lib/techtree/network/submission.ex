defmodule Techtree.Network.Submission do
  @moduledoc """
  One run somebody published, and everything the site is willing to say about
  it.

  Every column here was either recomputed from bytes that verify or copied out
  of a document whose signature was checked first. Nothing a submitter wrote in
  prose is stored, because there is nowhere for prose to arrive: the submission
  is a proof bundle, and a proof bundle carries digests, scores and task
  hashes. That is not a moderation policy that has to be applied — it is the
  absence of anything to moderate.

  The identity of the publisher is the fingerprint of the key that signed the
  bundle and nothing else. `executor_kind` says which sort of key that is; today
  the only sort is a local Ed25519 key a participant made on their own machine.
  A later release may let somebody sign for an account on a chain instead, and
  that will be another value of this column rather than another column.

  `raw_payload` is the exact bytes the site was handed, kept so that anybody can
  fetch them back and redo every check offline without taking this site's word
  for any of it. `bundle_digest` is not the digest of those bytes: it is the
  bundle's own `payload_digest`, recomputed here from the payload's canonical
  form, which is what makes the same proof submitted twice the same entry
  however it was wrapped for transport.

  `task_deltas` is a list rather than a scalar because its order is the
  Campaign's committed task order, checked against the Campaign this site
  publishes. It is stored as one document column and read with the row, the way
  a catalog entry's projection is: the detail page needs all of it or none of
  it, and there is no query that would ever ask about one task.

  A withdrawn entry keeps every column it had. `withdrawn_at` is written from
  an appended `Techtree.Network.Withdrawal`, and there is no destroy action on
  this resource at all, so a published entry cannot be unpublished even by
  something holding a connection to the database through Ash.
  """

  use Ash.Resource,
    otp_app: :techtree,
    domain: Techtree.Network,
    data_layer: AshPostgres.DataLayer,
    authorizers: [Ash.Policy.Authorizer]

  postgres do
    table "network_submissions"
    repo Techtree.Repo

    custom_statements do
      # The log position is handed out by the database rather than counted in
      # Elixir, so two submissions arriving at once cannot be given the same
      # one.
      statement :network_submission_sequence do
        up "CREATE SEQUENCE network_submission_sequence"
        down "DROP SEQUENCE network_submission_sequence"
      end
    end
  end

  actions do
    defaults [:read]

    read :list_published do
      description "The log, newest arrival first, without the withdrawn entries."

      filter expr(is_nil(withdrawn_at))

      prepare build(sort: [sequence: :desc])
    end

    read :get_by_digest do
      description "One entry, by the digest of the bundle it published."
      get? true

      argument :bundle_digest, :string, allow_nil?: false

      filter expr(bundle_digest == ^arg(:bundle_digest))
    end

    create :record do
      description "Append one verified submission. Ingest only."

      accept [
        :sequence,
        :bundle_digest,
        :run_id,
        :campaign_spec_digest,
        :data_policy_digest,
        :climb_reference,
        :executor_kind,
        :executor_key_id,
        :executor_public_key,
        :subject_model,
        :subject_harness,
        :subject_harness_version,
        :baseline_mean,
        :candidate_mean,
        :absolute_delta,
        :wins,
        :losses,
        :ties,
        :task_count,
        :decision,
        :proof_grade,
        :verification_checks_run,
        :verification_checks_passed,
        :task_deltas,
        :raw_payload
      ]
    end

    update :mark_withdrawn do
      description "Record that an appended withdrawal took this entry off the log."
      accept []

      argument :withdrawn_at, :utc_datetime_usec, allow_nil?: false

      change set_attribute(:withdrawn_at, arg(:withdrawn_at))
    end
  end

  policies do
    policy action_type(:read) do
      authorize_if always()
    end

    policy action_type([:create, :update, :destroy, :action]) do
      forbid_if always()
    end
  end

  attributes do
    uuid_primary_key :id

    attribute :sequence, :integer do
      description "This entry's position in the append-only log."
      allow_nil? false
      public? true
    end

    attribute :bundle_digest, :string do
      description "The proof bundle's own payload digest, recomputed on arrival."
      allow_nil? false
      public? true
    end

    attribute :run_id, :string do
      description "The run identifier the signed bundle carries."
      allow_nil? false
      public? true
    end

    attribute :campaign_spec_digest, :string do
      description "The Campaign this run was of, which this site publishes."
      allow_nil? false
      public? true
    end

    attribute :data_policy_digest, :string do
      description "The data policy the run was carried out under."
      allow_nil? false
      public? true
    end

    attribute :climb_reference, :string do
      description "The public `slug@version` of the Climb that Campaign belongs to."
      allow_nil? false
      public? true
    end

    attribute :executor_kind, :atom do
      description "What sort of key signed this bundle."
      allow_nil? false
      public? true
      constraints one_of: [:local_ed25519]
    end

    attribute :executor_key_id, :string do
      description "The fingerprint of the signing key, which is its public half hashed."
      allow_nil? false
      public? true
    end

    attribute :executor_public_key, :string do
      description "The public half of the signing key, as the bundle spells it."
      allow_nil? false
      public? true
    end

    attribute :subject_model, :string do
      description "The model the Campaign pins for the agent under test."
      allow_nil? false
      public? true
    end

    attribute :subject_harness, :string do
      description "The agent host the Campaign pins."
      allow_nil? false
      public? true
    end

    attribute :subject_harness_version, :string do
      description "The version of that agent host the Campaign pins."
      allow_nil? false
      public? true
    end

    attribute :baseline_mean, :float do
      description "The mean reward of the run without the Skill."
      allow_nil? false
      public? true
    end

    attribute :candidate_mean, :float do
      description "The mean reward of the run with the Skill."
      allow_nil? false
      public? true
    end

    attribute :absolute_delta, :float do
      description "How far apart the two means are."
      allow_nil? false
      public? true
    end

    attribute :wins, :integer do
      description "Tasks the candidate scored higher on, recomputed from the task list."
      allow_nil? false
      public? true
      constraints min: 0
    end

    attribute :losses, :integer do
      description "Tasks the candidate scored lower on, recomputed from the task list."
      allow_nil? false
      public? true
      constraints min: 0
    end

    attribute :ties, :integer do
      description "Tasks the two runs scored the same on, recomputed from the task list."
      allow_nil? false
      public? true
      constraints min: 0
    end

    attribute :task_count, :integer do
      description "How many tasks both runs covered."
      allow_nil? false
      public? true
      constraints min: 0
    end

    attribute :decision, :string do
      description "What the signed report concluded."
      allow_nil? false
      public? true
    end

    attribute :proof_grade, :string do
      description "What a result from this Climb may be presented as."
      allow_nil? false
      public? true
    end

    attribute :verification_checks_run, :integer do
      description "How many checks this site ran before accepting the submission."
      allow_nil? false
      public? true
      constraints min: 1
    end

    attribute :verification_checks_passed, :integer do
      description "How many of those checks passed."
      allow_nil? false
      public? true
      constraints min: 1
    end

    attribute :task_deltas, {:array, :map} do
      description "Both sides' reward for every task, in the Campaign's committed order."
      allow_nil? false
      default []
      public? true
    end

    attribute :raw_payload, :binary do
      description "The exact bytes this site was handed, served back for offline checking."
      allow_nil? false
      public? true
    end

    attribute :withdrawn_at, :utc_datetime_usec do
      description "When an appended withdrawal took this entry off the log."
      public? true
    end

    create_timestamp :inserted_at
    update_timestamp :updated_at
  end

  relationships do
    has_many :withdrawals, Techtree.Network.Withdrawal do
      description "The withdrawal events appended against this entry."
      public? true
    end
  end

  identities do
    identity :unique_bundle_digest, [:bundle_digest]
    identity :unique_sequence, [:sequence]
  end
end
