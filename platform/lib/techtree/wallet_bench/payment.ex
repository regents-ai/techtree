defmodule Techtree.WalletBench.Payment do
  @moduledoc """
  One send from the bench's funder wallet on Base: the USDC or the ETH for gas
  that funds a money attempt. The spending record, kept in the shared database,
  so a machine reset never touches it.

  A send is written `signed`, with its signed bytes and hash, before it is ever
  broadcast, so sending again is the same transaction and never a second one.
  It ends `confirmed` or `reverted` from its receipt on Base, or `unknown` when
  no receipt came in time; an unknown send pauses all funding until an
  operator settles it from the chain (`:settle`) as `confirmed` or `dropped`.

  The database holds the limits that must never break: one send per funder
  nonce, and an address is funded with each token at most once, ever.
  """

  use Ash.Resource,
    otp_app: :techtree,
    domain: Techtree.WalletBench,
    data_layer: AshPostgres.DataLayer,
    authorizers: [Ash.Policy.Authorizer]

  postgres do
    table "wallet_bench_payments"
    repo Techtree.Repo

    references do
      reference :attempt, on_delete: :nothing, on_update: :nothing
    end
  end

  actions do
    defaults [:read]

    read :for_attempt do
      description "An attempt's sends, in nonce order."
      argument :attempt_id, :uuid, allow_nil?: false
      filter expr(attempt_id == ^arg(:attempt_id))
      prepare build(sort: [nonce: :asc])
    end

    create :sign do
      description "A signed send, kept before it is broadcast. Funding steps only."
      accept [:attempt_id, :token, :from, :to, :amount, :nonce, :raw, :hash]
      change set_attribute(:state, :signed)
    end

    update :confirm do
      description "Its receipt on Base succeeded. Funding steps only."
      accept [:block]
      change filter(expr(state == :signed))
      change set_attribute(:state, :confirmed)
    end

    update :revert do
      description "Its receipt on Base failed. Funding steps only."
      accept [:block]
      change filter(expr(state == :signed))
      change set_attribute(:state, :reverted)
    end

    update :lose do
      description "No receipt came in time. Funding steps only."
      change filter(expr(state == :signed))
      change set_attribute(:state, :unknown)
    end

    update :settle do
      description """
      An operator, having read the chain, says what became of an unknown send:
      `confirmed` at a block, or `dropped`. Operator only.
      """

      accept [:block, :note]
      argument :state, :atom, allow_nil?: false, constraints: [one_of: [:confirmed, :dropped]]
      validate present(:note)
      change filter(expr(state == :unknown))
      change set_attribute(:state, arg(:state))
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

    attribute :token, :atom do
      allow_nil? false
      public? true
      constraints one_of: [:usdc, :eth]
    end

    attribute :state, :atom do
      allow_nil? false
      public? true
      constraints one_of: [:signed, :confirmed, :reverted, :unknown, :dropped]
    end

    attribute :from, :string, allow_nil?: false, public?: true, description: "The funder."
    attribute :to, :string, allow_nil?: false, public?: true, description: "The agent's address."

    attribute :amount, :integer do
      description "In units of 0.000001 USDC, or in wei."
      allow_nil? false
      public? true
      constraints min: 1
    end

    attribute :nonce, :integer, allow_nil?: false, public?: true, constraints: [min: 0]

    attribute :raw, :string,
      allow_nil?: false,
      public?: true,
      description: "The signed transaction, as broadcast."

    attribute :hash, :string, allow_nil?: false, public?: true
    attribute :block, :integer, public?: true, description: "The block its receipt is in."
    attribute :note, :string, public?: true, description: "What the operator read on the chain."

    timestamps()
  end

  relationships do
    belongs_to :attempt, Techtree.WalletBench.Attempt do
      allow_nil? false
      public? true
    end
  end

  identities do
    identity :one_send_per_nonce, [:from, :nonce]
    identity :fund_once, [:to, :token]
  end
end
