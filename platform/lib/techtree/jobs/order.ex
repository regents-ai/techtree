defmodule Techtree.Jobs.Order do
  @moduledoc """
  One job a signed-in agent asks Techtree's team for, in one of the four lanes,
  with what it is and what success looks like. The agent's person is kept on
  the order when the agent is paired with them.

  An order moves through its states one way:

    * requested, then checking once the team picks it up;
    * quoted, when the team sets its price (in USDC's millionths), what the
      price covers and until when it stands; the quote gives the order its
      payment reference (`Techtree.Jobs.Payment`);
    * paid, once the deposits saved with that reference add up to the quote,
      or expired, when the reading of Base passes a block made after the
      quote's expiry with too little paid (`Techtree.Jobs.Order.Settle`);
    * refused by the team before it is quoted, or cancelled by whoever asked
      before it is paid.

  Running, waiting on a decision, delivered and failed are states the order
  will reach once the work itself is tracked; nothing moves an order into them
  yet.

  The requesting agent, its person and the site's admins read the order and
  its quote; nobody else finds it. Only the admins check, quote and refuse.
  Whoever pays signs the calls themselves: the site never signs or sends
  anything. The site's payment reader (`Techtree.Jobs.Reader`) alone settles
  an order; the agent or the team may ask it to read Base again soon
  (`look_now`).
  """

  use Ash.Resource,
    otp_app: :techtree,
    domain: Techtree.Jobs,
    data_layer: AshPostgres.DataLayer,
    authorizers: [Ash.Policy.Authorizer],
    extensions: [AshStateMachine]

  alias Techtree.Jobs.Order.{SetQuote, SetRequester, Settle}

  @quote_fields "quote_amount, quote_scope, quote_expires_at, payment_reference"

  postgres do
    table "job_orders"
    repo Techtree.Repo

    check_constraints do
      # A quote is set whole or not at all.
      check_constraint :quote_amount, "quote_whole",
        check:
          "num_nulls(#{@quote_fields}) = 4 OR (num_nulls(#{@quote_fields}) = 0 AND quote_amount > 0)",
        message: "is set whole or not at all"
    end

    custom_indexes do
      # The quoted orders whose quote ran out, looked for on every pass that
      # reaches the head.
      index [:quote_expires_at], where: "state = 'quoted'"
    end
  end

  state_machine do
    initial_states([:requested])
    default_initial_state(:requested)
    # Reached once the work itself is tracked.
    extra_states([:running, :awaiting_decision, :delivered, :failed])

    transitions do
      transition(:check, from: :requested, to: :checking)
      transition(:set_quote, from: :checking, to: :quoted)
      transition(:refuse, from: [:requested, :checking], to: :refused)
      transition(:cancel, from: [:requested, :checking, :quoted], to: :cancelled)
      transition(:settle, from: :quoted, to: [:paid, :expired])
    end
  end

  actions do
    defaults [:read]

    # The quoted orders a stretch of the payment reader may move on: those
    # whose reference a deposit it saved carries, and, once it has passed a
    # block made at `passed_at`, those whose quote ran out before then.
    read :due do
      argument :references, {:array, :string}, allow_nil?: false
      argument :passed_at, :utc_datetime_usec

      filter expr(
               state == :quoted and
                 (payment_reference in ^arg(:references) or
                    quote_expires_at < ^arg(:passed_at))
             )
    end

    create :request do
      accept [:lane, :title, :success]
      change SetRequester
    end

    update :check do
      accept []
      change transition_state(:checking)
      change set_attribute(:checking_at, &DateTime.utc_now/0)
    end

    update :set_quote do
      accept [:quote_amount, :quote_scope, :quote_expires_at]
      require_attributes [:quote_amount, :quote_scope, :quote_expires_at]
      change transition_state(:quoted)
      change set_attribute(:quoted_at, &DateTime.utc_now/0)
      change SetQuote
    end

    update :refuse do
      accept []
      change transition_state(:refused)
      change set_attribute(:refused_at, &DateTime.utc_now/0)
    end

    update :cancel do
      accept []
      change transition_state(:cancelled)
      change set_attribute(:cancelled_at, &DateTime.utc_now/0)
    end

    # Asks the payment reader to read Base again soon (`Techtree.Jobs.Watch`).
    update :look_now do
      accept []
      require_atomic? false
      validate attribute_in(:state, [:quoted, :expired])

      change after_action(fn _changeset, order, _context ->
               Techtree.Jobs.Watch.refresh()
               {:ok, order}
             end)
    end

    update :settle do
      accept []
      argument :passed_at, :utc_datetime_usec
      require_atomic? false
      change Settle
    end
  end

  policies do
    policy action(:request) do
      authorize_if actor_attribute_equals(:role, :agent)
    end

    # The agent that asked, its person, and the team; nobody else finds it.
    policy action(:read) do
      authorize_if RegentAgents.Checks.Admin
      authorize_if expr(agent_id == ^actor(:agent_id))
      authorize_if expr(^actor(:role) == :human and human_account_id == ^actor(:human_account_id))
    end

    policy action([:check, :set_quote, :refuse]) do
      access_type :strict
      authorize_if RegentAgents.Checks.Admin
    end

    policy action(:cancel) do
      authorize_if expr(agent_id == ^actor(:agent_id))
      authorize_if expr(^actor(:role) == :human and human_account_id == ^actor(:human_account_id))
    end

    policy action(:look_now) do
      authorize_if RegentAgents.Checks.Admin
      authorize_if expr(agent_id == ^actor(:agent_id))
    end

    # Only the payment reader finds the orders it may move on, and moves them.
    policy action([:due, :settle]) do
      authorize_if actor_attribute_equals(:role, :system)
    end
  end

  attributes do
    uuid_primary_key :id

    attribute :lane, :atom,
      allow_nil?: false,
      public?: true,
      constraints: [one_of: [:skills, :evals, :environments, :models]]

    attribute :title, :string, allow_nil?: false, public?: true, constraints: [max_length: 200]
    attribute :success, :string, allow_nil?: false, public?: true, constraints: [max_length: 2000]

    # The quote: USDC's millionths, what it covers and until when it stands.
    attribute :quote_amount, :integer, public?: true, constraints: [min: 1]
    attribute :quote_scope, :string, public?: true, constraints: [max_length: 2000]
    attribute :quote_expires_at, :utc_datetime_usec, public?: true

    attribute :payment_reference, :string,
      public?: true,
      constraints: [match: ~r/\A0x[0-9a-f]{64}\z/]

    create_timestamp :requested_at, public?: true
    attribute :checking_at, :utc_datetime_usec, public?: true
    attribute :quoted_at, :utc_datetime_usec, public?: true
    attribute :paid_at, :utc_datetime_usec, public?: true
    attribute :refused_at, :utc_datetime_usec, public?: true
    attribute :expired_at, :utc_datetime_usec, public?: true
    attribute :cancelled_at, :utc_datetime_usec, public?: true
  end

  relationships do
    belongs_to :agent, Techtree.Agents.Agent do
      allow_nil? false
      public? true
    end

    # The agent's person, when it was paired as it asked.
    belongs_to :human_account, Techtree.Accounts.HumanAccount do
      attribute_type :integer
      public? true
    end

    # Every deposit saved with the order's payment reference.
    has_many :deposits, Techtree.Jobs.Deposit do
      source_attribute :payment_reference
      destination_attribute :reference
      public? true
    end
  end

  aggregates do
    # Everything deposited with the order's reference, in USDC's millionths.
    sum :received, :deposits, :amount do
      public? true
      default 0
    end
  end

  identities do
    identity :unique_payment_reference, [:payment_reference]
  end
end
