defmodule Techtree.Jobs.Deposit do
  @moduledoc """
  One job payment exactly as Base first gave it (`Techtree.Jobs.Scanner`): a
  `USDCRevenueDeposited` log from REGENT revenue staking, a direct deposit
  tagged `techtree.job`. It keeps the chain, the contract, the transaction and
  the log within it, the block and its hash, the wallet that sent it, the
  reference it carried and the USDC received in millionths. The sending wallet
  is recorded and never checked: anyone may pay an order. A deposit whose
  reference matches no order is saved all the same, with no order.

  A row is written once and never changed or removed: saved again, it stays as
  first saved. The order's agent, its person and the site's admins read an
  order's deposits; only the admins read one that matches no order.
  """

  use Ash.Resource,
    otp_app: :techtree,
    domain: Techtree.Jobs,
    data_layer: AshPostgres.DataLayer,
    authorizers: [Ash.Policy.Authorizer]

  @address ~r/\A0x[0-9a-f]{40}\z/
  @hash ~r/\A0x[0-9a-f]{64}\z/

  postgres do
    table "job_deposits"
    repo Techtree.Repo

    references do
      # A deposit may carry a reference no order has.
      reference :order, ignore?: true
    end

    custom_indexes do
      # An order's deposits, by its reference: what it has received.
      index [:reference]
      # The rows a stretch reads again, by block.
      index [:chain_id, :contract, :block_number]
    end
  end

  actions do
    defaults [:read]

    # The rows already saved from one contract that a stretch reads again:
    # those in blocks `from` to `to`, and every row of the `transactions` it
    # read, wherever they were saved.
    read :seen do
      argument :chain_id, :integer, allow_nil?: false
      argument :contract, :string, allow_nil?: false, constraints: [match: @address]
      argument :from, :integer, allow_nil?: false
      argument :to, :integer, allow_nil?: false
      argument :transactions, {:array, :string}, allow_nil?: false

      filter expr(
               chain_id == ^arg(:chain_id) and contract == ^arg(:contract) and
                 ((block_number >= ^arg(:from) and block_number <= ^arg(:to)) or
                    transaction_hash in ^arg(:transactions))
             )
    end

    create :record do
      accept [
        :chain_id,
        :contract,
        :transaction_hash,
        :log_index,
        :block_number,
        :block_hash,
        :depositor,
        :reference,
        :amount
      ]

      upsert? true
      upsert_identity :unique_chain_event
      upsert_fields []
      upsert_condition expr(false)
      return_skipped_upsert? true
    end
  end

  policies do
    # Only the payment reader saves deposits and reads them back to compare.
    policy action([:record, :seen]) do
      authorize_if actor_attribute_equals(:role, :system)
    end

    policy action(:read) do
      authorize_if RegentAgents.Checks.Admin
      authorize_if expr(order.agent_id == ^actor(:agent_id))

      authorize_if expr(
                     ^actor(:role) == :human and
                       order.human_account_id == ^actor(:human_account_id)
                   )
    end
  end

  attributes do
    uuid_primary_key :id
    attribute :chain_id, :integer, allow_nil?: false, public?: true, constraints: [min: 1]
    attribute :contract, :string, allow_nil?: false, public?: true, constraints: [match: @address]

    attribute :transaction_hash, :string,
      allow_nil?: false,
      public?: true,
      constraints: [match: @hash]

    attribute :log_index, :integer, allow_nil?: false, public?: true, constraints: [min: 0]
    attribute :block_number, :integer, allow_nil?: false, public?: true, constraints: [min: 0]
    attribute :block_hash, :string, allow_nil?: false, public?: true, constraints: [match: @hash]

    attribute :depositor, :string,
      allow_nil?: false,
      public?: true,
      constraints: [match: @address]

    attribute :reference, :string, allow_nil?: false, public?: true, constraints: [match: @hash]
    # The USDC the staking contract received, in millionths.
    attribute :amount, :decimal, allow_nil?: false, public?: true, constraints: [min: 0]
    create_timestamp :recorded_at, public?: true
  end

  relationships do
    # The order whose payment reference the deposit carried, if one has it.
    belongs_to :order, Techtree.Jobs.Order do
      source_attribute :reference
      destination_attribute :payment_reference
      define_attribute? false
      public? true
    end
  end

  identities do
    identity :unique_chain_event, [:chain_id, :transaction_hash, :log_index]
  end
end
