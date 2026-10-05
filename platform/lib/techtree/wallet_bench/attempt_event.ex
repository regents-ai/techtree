defmodule Techtree.WalletBench.AttemptEvent do
  @moduledoc """
  What happened in one attempt, in the order it happened: each state the
  attempt reached and each state each of its turns reached.

  An event is written in the same transaction as the change it records
  (`Techtree.WalletBench.Attempt.Changes.RecordEvent`), so a step that rolled
  back left no event. `step` names the state, such as `leased` or
  `T1a judged`; `detail` holds what that step saw. Events are appended and
  never changed.
  """

  use Ash.Resource,
    otp_app: :techtree,
    domain: Techtree.WalletBench,
    data_layer: AshPostgres.DataLayer,
    authorizers: [Ash.Policy.Authorizer],
    notifiers: [Ash.Notifier.PubSub]

  postgres do
    table "wallet_bench_attempt_events"
    repo Techtree.Repo

    references do
      reference :attempt, on_delete: :nothing, on_update: :nothing
    end

    custom_indexes do
      index [:attempt_id, :inserted_at]
    end
  end

  actions do
    defaults [:read]

    read :for_attempt do
      description "Everything that happened in one attempt, oldest first."
      argument :attempt_id, :uuid, allow_nil?: false
      filter expr(attempt_id == ^arg(:attempt_id))
      prepare build(sort: [inserted_at: :asc])
    end

    create :record do
      description "Append one event. Attempt and turn steps only."
      accept [:attempt_id, :step, :detail]
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

  pub_sub do
    module TechtreeWeb.Endpoint
    prefix "wallet_bench"
    publish :record, ["attempts", :attempt_id]
  end

  attributes do
    uuid_primary_key :id

    attribute :step, :string do
      allow_nil? false
      public? true
      constraints max_length: 64
    end

    attribute :detail, :map, allow_nil?: false, default: %{}, public?: true

    create_timestamp :inserted_at
  end

  relationships do
    belongs_to :attempt, Techtree.WalletBench.Attempt do
      allow_nil? false
      public? true
    end
  end
end
