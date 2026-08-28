defmodule Techtree.Network.PublicationEntry do
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
  bundle and nothing else. `participant_kind` says which sort of key that is;
  today the only sort is a local Ed25519 key a participant made on their own
  machine. A later release may let somebody sign for an account on a chain
  instead, and that will be another value of this column rather than another
  column.

  ## The row is written once and never rewritten

  There is no update action here but the one that records that a signed
  withdrawal arrived, and there is no destroy action at all. Everything an
  entry will ever say is written in the single insert that creates it —
  including its own log sequence, when it was accepted, and the receipt this
  site handed back — because a row that is completed by a second write is a row
  that can exist half-written.

  That is also what makes the retry safe. `log_sequence`, `id` and `accepted_at`
  are chosen before the insert, the receipt is built and signed over them, and
  the whole of it goes in at once. If two identical publications race, the one
  that loses the unique index on `bundle_digest` throws away the receipt it
  built and hands back the receipt the winner stored. Nobody gets a second row
  and nobody gets a second receipt.

  ## What is stored, and what is not served

  `submission_bytes` is the exact bytes this site was handed. They are kept so
  that every published field can be re-derived from them by anybody with access
  to them, and they are **not** served: a public address returning the file
  mapping hands over the whole bundle however it is wrapped in JSON, and
  decision 0038 defers that. `submission_digest` is the digest of the canonical
  form of that document, and it is the one thing that tells a lost-response
  retry apart from a different submission wearing the same bundle digest.

  `bundle_digest` is not the digest of those bytes: it is the bundle's own
  `payload_digest`, recomputed from the payload's canonical form, which is what
  makes the same proof submitted twice the same entry however it was wrapped
  for transport. It is also the address the entry lives at, so the URL is
  derivable from the proof itself and two people publishing the same bundle
  land on the same page.

  `task_deltas` is a list rather than a scalar because its order is the
  Campaign's committed task order, checked against the Campaign this site
  publishes. It is stored as one document column and read with the row, the way
  a catalog entry's projection is: the detail page needs all of it or none of
  it, and there is no query that would ever ask about one task.

  A withdrawn entry keeps every column it had, and keeps its place on the log.
  `withdrawn_at` is written from an appended `Techtree.Network.PublicationEvent`,
  so a published entry cannot be unpublished even by something holding a
  connection to the database through Ash.
  """

  use Ash.Resource,
    otp_app: :techtree,
    domain: Techtree.Network,
    data_layer: AshPostgres.DataLayer,
    authorizers: [Ash.Policy.Authorizer]

  postgres do
    table "network_publication_entries"
    repo Techtree.Repo

    custom_statements do
      # The log sequence is handed out by the database rather than counted in
      # Elixir, so two submissions arriving at once cannot be given the same
      # one. It may have gaps — a publication that loses a race has already
      # taken a number — and a sequence with gaps is still a sequence. It is
      # not a position and it is not a rank.
      statement :network_publication_sequence do
        up "CREATE SEQUENCE network_publication_sequence"
        down "DROP SEQUENCE network_publication_sequence"
      end
    end
  end

  actions do
    defaults [:read]

    read :list_log do
      description "The log, newest arrival first, from a sequence the caller already holds."

      argument :before_sequence, :integer, allow_nil?: true

      filter expr(is_nil(^arg(:before_sequence)) or log_sequence < ^arg(:before_sequence))

      prepare build(sort: [log_sequence: :desc])
    end

    read :get_by_digest do
      description "One entry, by the digest of the bundle it published."
      get? true

      argument :bundle_digest, :string, allow_nil?: false

      filter expr(bundle_digest == ^arg(:bundle_digest))
    end

    read :get_by_run do
      description "One entry, by the participant and run it belongs to."
      get? true

      argument :participant_key_id, :string, allow_nil?: false
      argument :run_id, :string, allow_nil?: false

      filter expr(participant_key_id == ^arg(:participant_key_id) and run_id == ^arg(:run_id))
    end

    create :record do
      description "Append one verified publication, whole. Ingest only."

      accept [
        :id,
        :log_sequence,
        :accepted_at,
        :bundle_digest,
        :submission_bytes,
        :submission_digest,
        :run_id,
        :campaign_spec_digest,
        :data_policy_digest,
        :climb_reference,
        :participant_kind,
        :participant_key_id,
        :participant_public_key,
        :subject_provider,
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
        :statuses,
        :decision,
        :proof_grade,
        :verification_checks_run,
        :verification_checks_passed,
        :task_deltas,
        :receipt_bytes,
        :receipt_digest,
        :network_key_id
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
    uuid_primary_key :id, writable?: true

    attribute :log_sequence, :integer do
      description "Where this entry landed in the append-only log."
      allow_nil? false
      public? true
    end

    attribute :accepted_at, :utc_datetime_usec do
      description "When this log accepted the publication."
      allow_nil? false
      public? true
    end

    attribute :bundle_digest, :string do
      description "The proof bundle's own payload digest, recomputed on arrival."
      allow_nil? false
      public? true
    end

    attribute :submission_bytes, :binary do
      description "The exact bytes this site was handed. Stored, never served."
      allow_nil? false
      public? false
    end

    attribute :submission_digest, :string do
      description "The digest of the canonical form of the submitted document."
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

    attribute :participant_kind, :atom do
      description "What sort of key signed this bundle."
      allow_nil? false
      public? true
      constraints one_of: [:local_ed25519]
    end

    attribute :participant_key_id, :string do
      description "The fingerprint of the signing key, which is its public half hashed."
      allow_nil? false
      public? true
    end

    attribute :participant_public_key, :string do
      description "The public half of the signing key, as the bundle spells it."
      allow_nil? false
      public? true
    end

    attribute :subject_provider, :string do
      description "The inference provider the Campaign pins for the agent under test."
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

    attribute :statuses, :map do
      description "The five statuses the signed report closed with."
      allow_nil? false
      default %{}
      public? true
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

    attribute :receipt_bytes, :binary do
      description "The countersigned receipt this site handed back, byte for byte."
      allow_nil? false
      public? false
    end

    attribute :receipt_digest, :string do
      description "The digest of that receipt's own signed payload."
      allow_nil? false
      public? true
    end

    attribute :network_key_id, :string do
      description "The fingerprint of the key this site countersigned with."
      allow_nil? false
      public? true
    end

    attribute :withdrawn_at, :utc_datetime_usec do
      description "When an appended withdrawal marked this entry withdrawn."
      public? true
    end
  end

  relationships do
    has_many :events, Techtree.Network.PublicationEvent do
      description "The events appended against this entry, acceptance first."
      public? true
    end
  end

  identities do
    identity :unique_bundle_digest, [:bundle_digest]
    identity :unique_log_sequence, [:log_sequence]
    identity :unique_participant_run, [:participant_key_id, :run_id]
  end
end
