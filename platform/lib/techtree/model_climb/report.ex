defmodule Techtree.ModelClimb.Report do
  @moduledoc """
  A Model Climb proof a person's paired agent sent, kept privately for that
  person (contract `docs/spec/model-climb-v1.md`, section 3.5; Sean,
  TT-BYO-MC-PRIVATE a, 13 Oct 2026).

  Only `submit` writes one, and only after `Techtree.ModelClimb.Proof` has
  checked it; every column is read out of the checked proof or the agent's
  current pairing, never from anything else the request says. Only the owner's
  paired agents read it. Sending the same proof again answers with the record
  already kept; reusing an `Idempotency-Key` for a different proof is refused
  by the owner-and-key identity.
  """

  use Ash.Resource,
    otp_app: :techtree,
    domain: Techtree.ModelClimb,
    data_layer: AshPostgres.DataLayer,
    authorizers: [Ash.Policy.Authorizer]

  postgres do
    table "model_climb_reports"
    repo Techtree.Repo
  end

  actions do
    create :submit do
      accept []
      argument :proof, :map, allow_nil?: false
      argument :idempotency_key, :string, allow_nil?: false, constraints: [max_length: 255]

      upsert? true
      upsert_identity :unique_owner_report
      upsert_fields []

      change set_attribute(:owner_privy_user_id, actor(:privy_user_id))
      change set_attribute(:pairing_id, actor(:id))
      change set_attribute(:acting_agent_wallet, actor(:wallet))
      change set_attribute(:idempotency_key, arg(:idempotency_key))
      change Techtree.ModelClimb.Report.Verify
    end

    read :mine do
      prepare build(sort: [inserted_at: :desc])
    end

    read :mine_by_digest do
      get? true
      argument :report_digest, :string, allow_nil?: false
      filter expr(report_digest == ^arg(:report_digest))
    end
  end

  policies do
    policy action(:submit) do
      authorize_if actor_present()
    end

    policy action_type(:read) do
      authorize_if expr(owner_privy_user_id == ^actor(:privy_user_id))
    end
  end

  attributes do
    uuid_primary_key :id

    attribute :owner_privy_user_id, :string, allow_nil?: false, sensitive?: true
    attribute :pairing_id, :string, allow_nil?: false
    attribute :acting_agent_wallet, :string, allow_nil?: false
    attribute :idempotency_key, :string, allow_nil?: false

    attribute :request_digest, :string, allow_nil?: false, public?: true
    attribute :report_digest, :string, allow_nil?: false, public?: true
    attribute :signer_key_id, :string, allow_nil?: false, public?: true
    attribute :results, :map, allow_nil?: false, public?: true
    attribute :paired_outcomes, :map, allow_nil?: false, public?: true
    attribute :proof, :binary, allow_nil?: false

    create_timestamp :inserted_at, public?: true
  end

  identities do
    identity :unique_owner_report, [:owner_privy_user_id, :report_digest]

    identity :unique_owner_key, [:owner_privy_user_id, :idempotency_key],
      field_names: [:idempotency_key],
      message: "was already used for a different proof"
  end
end
