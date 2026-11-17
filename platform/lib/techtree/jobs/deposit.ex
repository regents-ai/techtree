defmodule Techtree.Jobs.Deposit do
  @moduledoc """
  One deposit into REGENT revenue staking that carried a job order's payment
  reference, as it was read from Base (`Techtree.Jobs.Order.ReadPayment`): the
  transaction and the log within it, the wallet that sent it, the USDC it
  delivered in millionths, and its block. The sending wallet is recorded and
  never checked: anyone may pay an order.

  Each log is saved once and then kept as it was first read; reading it again
  changes nothing. The order's agent, its person and the site's admins read an
  order's deposits.
  """

  use Ash.Resource,
    otp_app: :techtree,
    domain: Techtree.Jobs,
    data_layer: AshPostgres.DataLayer,
    authorizers: [Ash.Policy.Authorizer]

  postgres do
    table "job_deposits"
    repo Techtree.Repo

    custom_indexes do
      # An order's deposits, summed on every read of its payments.
      index [:order_id]
    end
  end

  actions do
    defaults [:read]

    create :record do
      accept [:transaction_hash, :log_index, :depositor, :amount, :block_number, :order_id]
      upsert? true
      upsert_identity :unique_log
      # First read wins; a log read again is left as it is.
      upsert_fields []
    end
  end

  policies do
    # Only an order's payment read records its deposits.
    policy action(:record) do
      authorize_if actor_attribute_equals(:role, :system)
    end

    policy action_type(:read) do
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

    attribute :transaction_hash, :string,
      allow_nil?: false,
      public?: true,
      constraints: [match: ~r/\A0x[0-9a-f]{64}\z/]

    attribute :log_index, :integer, allow_nil?: false, public?: true, constraints: [min: 0]

    attribute :depositor, :string,
      allow_nil?: false,
      public?: true,
      constraints: [match: ~r/\A0x[0-9a-f]{40}\z/]

    # The USDC the staking contract received, in millionths.
    attribute :amount, :decimal, allow_nil?: false, public?: true, constraints: [min: 0]
    attribute :block_number, :integer, allow_nil?: false, public?: true, constraints: [min: 0]
    create_timestamp :recorded_at, public?: true
  end

  relationships do
    belongs_to :order, Techtree.Jobs.Order do
      allow_nil? false
      public? true
    end
  end

  identities do
    identity :unique_log, [:transaction_hash, :log_index]
  end
end
