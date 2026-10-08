defmodule Techtree.WalletBench.Attempt do
  @moduledoc """
  One run of one pair: a harness and a wallet, tested on a machine of their own.

  `state` moves forward one step per job: `requested`, `leased` (a ready
  machine with today's recipe is taken for it), `testing` (the model key is on
  the machine and the turns run, `Techtree.WalletBench.Turn`), `revoking` (the
  tests are over or one failed; the key comes off) and `done`, or `failed` with
  the reason.

  An attempt of the `money` plan (only on `Catalog.money_pair?/2` pairs) goes
  on after a passed wallet test: `funding` (the bench signs 0.25 USDC and
  0.00003 ETH for the agent's address, `Techtree.WalletBench.Funding`),
  `sending` (the sends are broadcast and their receipts read), then `testing`
  again for T3, T4, T5 and the turn that returns what is left. When the agent
  did not pass the install and wallet tests that funding needs, the reason is
  kept in `funding_refused` and the attempt ends as usual; when the bench
  itself cannot fund it, the attempt fails with the reason.

  Every attempt that reached a machine goes through `revoking`:
  once the key is confirmed gone, the machine is reset for the next attempt;
  when it cannot be confirmed gone, the machine is deleted instead. A `done`
  attempt the bench itself spoiled is withdrawn: `failed`, with the reason.

  Each step calls the machine before its transaction opens, then writes the new
  state, its `Techtree.WalletBench.AttemptEvent` and the next step's job in one
  transaction. A step changes the attempt only if it is still in the state the
  step follows.
  """

  use Ash.Resource,
    otp_app: :techtree,
    domain: Techtree.WalletBench,
    data_layer: AshPostgres.DataLayer,
    authorizers: [Ash.Policy.Authorizer],
    extensions: [AshOban],
    notifiers: [Ash.Notifier.PubSub]

  alias Techtree.WalletBench.Attempt.Changes.{
    AttachCredentials,
    LeaseMachine,
    RecordEvent,
    ReleaseMachine,
    RevokeCredentials,
    RunTriggerForState,
    SendFunding,
    SignFunding
  }

  alias Techtree.WalletBench.{Catalog, Machine}

  postgres do
    table "wallet_bench_attempts"
    repo Techtree.Repo

    references do
      reference :machine, on_delete: :nothing, on_update: :nothing
    end
  end

  oban do
    triggers do
      trigger :lease do
        action :lease
        where expr(state == :requested)
        queue(:sprites)
        max_attempts(5)
        on_error(:mark_failed)
        lock_for_update?(false)
        scheduler_cron(false)
        worker_module_name(Techtree.WalletBench.Attempt.Workers.Lease)
      end

      trigger :attach_credentials do
        action :attach_credentials
        where expr(state == :leased)
        queue(:sprites)
        max_attempts(5)
        on_error(:stop)
        lock_for_update?(false)
        scheduler_cron(false)
        worker_module_name(Techtree.WalletBench.Attempt.Workers.AttachCredentials)
      end

      trigger :sign_funding do
        action :sign_funding
        where expr(state == :funding)
        queue(:wallet_bench_funding)
        max_attempts(3)
        on_error(:funding_failed)
        lock_for_update?(false)
        scheduler_cron(false)
        worker_module_name(Techtree.WalletBench.Attempt.Workers.SignFunding)
      end

      trigger :send_funding do
        action :send_funding
        where expr(state == :sending)
        queue(:wallet_bench_funding)
        max_attempts(10)
        on_error(:sending_failed)
        lock_for_update?(false)
        scheduler_cron(false)
        worker_module_name(Techtree.WalletBench.Attempt.Workers.SendFunding)
      end

      trigger :revoke do
        action :revoke
        where expr(state == :revoking)
        queue(:sprites)
        max_attempts(5)
        on_error(:revoke_failed)
        lock_for_update?(false)
        scheduler_cron(false)
        worker_module_name(Techtree.WalletBench.Attempt.Workers.Revoke)
      end
    end
  end

  actions do
    defaults [:read]

    read :recent do
      description "Every attempt, newest first."
      prepare build(sort: [inserted_at: :desc])
    end

    create :request do
      description "Ask for one pair to be tested; jobs take it from here. Operator only."
      accept [:harness_id, :wallet_id, :plan]
      validate one_of(:harness_id, Catalog.harness_ids())
      validate one_of(:wallet_id, Catalog.tested_wallet_ids())

      validate fn changeset, _context ->
        plan = Ash.Changeset.get_attribute(changeset, :plan)
        harness_id = Ash.Changeset.get_attribute(changeset, :harness_id)
        wallet_id = Ash.Changeset.get_attribute(changeset, :wallet_id)

        if plan == :money and not Catalog.money_pair?(harness_id, wallet_id),
          do: {:error, field: :plan, message: "the money tests do not run on this pair"},
          else: :ok
      end

      change set_attribute(:state, :requested)
      change RecordEvent
      change run_oban_trigger(:lease)
    end

    update :lease do
      description "Takes a ready machine, or waits for one."
      require_atomic? false
      change filter(expr(state == :requested))
      change LeaseMachine
      change set_attribute(:state, :leased)
      change RecordEvent
      change run_oban_trigger(:attach_credentials)
    end

    update :attach_credentials do
      description "Puts the model key on the machine and queues the first test."
      require_atomic? false
      change filter(expr(state == :leased))
      change AttachCredentials
      change set_attribute(:state, :testing)
      change RecordEvent
    end

    update :finish_tests do
      description "The last test is judged. Turn steps only."
      require_atomic? false
      change filter(expr(state == :testing))
      change set_attribute(:state, :revoking)
      change RecordEvent
      change run_oban_trigger(:revoke)
    end

    update :fund do
      description "The wallet test passed on a money attempt; its address is funded next. Turn steps only."
      require_atomic? false
      argument :address, :string, allow_nil?: false
      change filter(expr(state == :testing and plan == :money))
      change set_attribute(:agent_address, arg(:address))
      change set_attribute(:state, :funding)
      change RecordEvent
      change run_oban_trigger(:sign_funding)
    end

    update :refuse_funding do
      description "A money attempt did not earn its funding, for the reason given; its tests are over. Turn steps only."
      require_atomic? false
      argument :reason, :string, allow_nil?: false
      change filter(expr(state == :testing and plan == :money))
      change set_attribute(:funding_refused, arg(:reason))
      change set_attribute(:state, :revoking)

      change fn changeset, _context ->
        RecordEvent.put_detail(changeset, %{
          funding_refused: Ash.Changeset.get_argument(changeset, :reason)
        })
      end

      change RecordEvent
      change run_oban_trigger(:revoke)
    end

    update :sign_funding do
      description "Signs the funding sends and keeps them, or says why the attempt is not funded."
      require_atomic? false
      change filter(expr(state == :funding))
      change SignFunding
      change RecordEvent
      change {RunTriggerForState, sending: :send_funding, revoking: :revoke}
    end

    update :funding_failed do
      description "Signing ran out of retries; nothing was sent, and the attempt stops."
      require_atomic? false
      argument :error, :term
      change filter(expr(state == :funding))
      change set_attribute(:state, :revoking)

      change fn changeset, _context ->
        message =
          "The bench could not sign the funding: " <>
            (changeset |> Ash.Changeset.get_argument(:error) |> Machine.describe_error())

        changeset
        |> Ash.Changeset.force_change_attribute(:failure, message)
        |> RecordEvent.put_detail(%{failure: message})
      end

      change RecordEvent
      change run_oban_trigger(:revoke)
    end

    update :send_funding do
      description "Broadcasts the signed sends and reads their receipts; T3 follows both."
      require_atomic? false
      change filter(expr(state == :sending))
      change SendFunding
      change RecordEvent
      change {RunTriggerForState, revoking: :revoke}
    end

    update :sending_failed do
      description """
      The receipts could not be read after every retry: the sends not yet
      settled become unknown, which pauses funding, and the attempt stops.
      """

      require_atomic? false
      argument :error, :term
      change filter(expr(state == :sending))
      change set_attribute(:state, :revoking)

      change fn changeset, _context ->
        message =
          "The funding sends' receipts could not be read, so their outcome is unknown and funding is paused: " <>
            (changeset |> Ash.Changeset.get_argument(:error) |> Machine.describe_error())

        changeset
        |> Ash.Changeset.force_change_attribute(:failure, message)
        |> RecordEvent.put_detail(%{failure: message})
        |> Ash.Changeset.after_action(fn _changeset, attempt ->
          with {:ok, payments} <- Techtree.WalletBench.list_payments(attempt.id) do
            payments
            |> Enum.filter(&(&1.state == :signed))
            |> Enum.reduce_while({:ok, attempt}, fn payment, {:ok, attempt} ->
              payment
              |> Ash.Changeset.for_update(:lose, %{})
              # Payments have no public writer; the attempt's own funding step is one of two.
              |> Ash.update(authorize?: false)
              |> case do
                {:ok, _payment} -> {:cont, {:ok, attempt}}
                {:error, error} -> {:halt, {:error, error}}
              end
            end)
          end
        end)
      end

      change RecordEvent
      change run_oban_trigger(:revoke)
    end

    update :clear_safety_stop do
      description """
      After a money test's safety failure on this attempt paused all funding,
      an operator lets funding go on, saying why. Operator only.
      """

      require_atomic? false
      argument :note, :string, allow_nil?: false
      change filter(expr(plan == :money and is_nil(safety_cleared)))
      change set_attribute(:safety_cleared, arg(:note))
    end

    update :stop do
      description "A step could not go on; the key still comes off. Attempt and turn steps only."
      require_atomic? false
      argument :error, :term
      change filter(expr(state in [:leased, :testing]))
      change set_attribute(:state, :revoking)

      change fn changeset, _context ->
        message = changeset |> Ash.Changeset.get_argument(:error) |> Machine.describe_error()

        changeset
        |> Ash.Changeset.force_change_attribute(:failure, message)
        |> RecordEvent.put_detail(%{failure: message})
      end

      change RecordEvent
      change run_oban_trigger(:revoke)
    end

    update :revoke do
      description "Takes the key off the machine, then resets the machine."
      require_atomic? false
      change filter(expr(state == :revoking))
      change RevokeCredentials

      change fn changeset, _context ->
        state = if changeset.data.failure, do: :failed, else: :done
        Ash.Changeset.force_change_attribute(changeset, :state, state)
      end

      change RecordEvent
      change {ReleaseMachine, to: :reset}
    end

    update :revoke_failed do
      description "The key could not be confirmed removed; the machine is deleted instead."
      require_atomic? false
      argument :error, :term
      change filter(expr(state == :revoking))
      change set_attribute(:state, :failed)

      change fn changeset, _context ->
        message =
          "The model key could not be confirmed removed, so the machine is being deleted: " <>
            (changeset |> Ash.Changeset.get_argument(:error) |> Machine.describe_error())

        changeset
        |> Ash.Changeset.force_change_attribute(:failure, message)
        |> RecordEvent.put_detail(%{failure: message})
      end

      change RecordEvent
      change {ReleaseMachine, to: :retire}
    end

    update :mark_failed do
      description "No machine could be taken."
      require_atomic? false
      argument :error, :term
      change filter(expr(state == :requested))
      change set_attribute(:state, :failed)

      change fn changeset, _context ->
        message = changeset |> Ash.Changeset.get_argument(:error) |> Machine.describe_error()

        changeset
        |> Ash.Changeset.force_change_attribute(:failure, message)
        |> RecordEvent.put_detail(%{failure: message})
      end

      change RecordEvent
    end

    update :withdraw do
      description """
      A finished attempt the bench itself spoiled leaves the results, with the
      reason; its record stays. Operator only.
      """

      require_atomic? false
      argument :reason, :string, allow_nil?: false
      change filter(expr(state == :done))
      change set_attribute(:state, :failed)

      change fn changeset, _context ->
        reason = Ash.Changeset.get_argument(changeset, :reason)

        changeset
        |> Ash.Changeset.force_change_attribute(:failure, reason)
        |> RecordEvent.put_detail(%{failure: reason})
      end

      change RecordEvent
    end
  end

  policies do
    bypass AshOban.Checks.AshObanInteraction do
      authorize_if always()
    end

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
    publish_all :create, ["attempts"]
    publish_all :update, ["attempts"]
  end

  attributes do
    uuid_primary_key :id

    attribute :harness_id, :string, allow_nil?: false, public?: true
    attribute :wallet_id, :string, allow_nil?: false, public?: true

    attribute :state, :atom do
      allow_nil? false
      public? true

      constraints one_of: [
                    :requested,
                    :leased,
                    :testing,
                    :funding,
                    :sending,
                    :revoking,
                    :done,
                    :failed
                  ]
    end

    attribute :plan, :atom do
      description "`wallet`: install and wallet tests. `money`: then funded, T3 to T5 and returning what is left."
      allow_nil? false
      public? true
      default :wallet
      constraints one_of: [:wallet, :money]
    end

    attribute :failure, :string, public?: true, description: "Why the attempt failed."

    attribute :agent_address, :string,
      public?: true,
      description: "The Base address the wallet test found, which the bench funds."

    attribute :funding_refused, :string,
      public?: true,
      description:
        "Why this money attempt was not funded: the install or wallet test it had to pass."

    attribute :safety_cleared, :string,
      public?: true,
      description:
        "Why an operator let funding go on after this attempt's money-test safety failure."

    timestamps()
  end

  relationships do
    belongs_to :machine, Machine, public?: true

    has_many :turns, Techtree.WalletBench.Turn do
      public? true
      sort inserted_at: :asc
    end

    has_many :payments, Techtree.WalletBench.Payment do
      public? true
      sort nonce: :asc
    end
  end

  aggregates do
    sum :model_spend_usd, :turns, :model_spend_usd, public?: true
    sum :judge_cost_usd, :turns, :judge_cost_usd, public?: true
  end
end
