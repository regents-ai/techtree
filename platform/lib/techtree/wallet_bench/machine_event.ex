defmodule Techtree.WalletBench.MachineEvent do
  @moduledoc """
  What happened to one machine, in the order it happened.

  An event is written in the same transaction as the machine's new state, so a
  step that rolled back left no event, and every state the machine reached has
  one. `step` is the state the machine moved to; `detail` holds what that step
  saw, such as the Sprites image version, the checkpoint id or each readiness
  check. Events are appended and never changed.
  """

  use Ash.Resource,
    otp_app: :techtree,
    domain: Techtree.WalletBench,
    data_layer: AshPostgres.DataLayer,
    authorizers: [Ash.Policy.Authorizer]

  postgres do
    table "wallet_bench_machine_events"
    repo Techtree.Repo

    references do
      reference :machine, on_delete: :nothing, on_update: :nothing
    end

    custom_indexes do
      index [:machine_id, :inserted_at]
    end
  end

  actions do
    defaults [:read]

    read :for_machine do
      description "Everything that happened to one machine, oldest first."
      argument :machine_id, :uuid, allow_nil?: false
      filter expr(machine_id == ^arg(:machine_id))
      prepare build(sort: [inserted_at: :asc])
    end

    create :record do
      description "Append one event. Machine steps only."
      accept [:machine_id, :step, :detail]
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

    attribute :step, :atom do
      allow_nil? false
      public? true

      constraints one_of: [
                    :requested,
                    :created,
                    :built,
                    :checkpointed,
                    :restored,
                    :settling,
                    :ready,
                    :leased,
                    :resetting,
                    :failed,
                    :retiring,
                    :retired
                  ]
    end

    attribute :detail, :map, allow_nil?: false, default: %{}, public?: true

    create_timestamp :inserted_at
  end

  relationships do
    belongs_to :machine, Techtree.WalletBench.Machine do
      allow_nil? false
      public? true
    end
  end
end
