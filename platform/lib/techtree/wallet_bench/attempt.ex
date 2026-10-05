defmodule Techtree.WalletBench.Attempt do
  @moduledoc """
  One run of one pair: a harness and a wallet, tested on a machine of their own.

  `state` moves forward one step per job: `requested`, `leased` (a ready
  machine with today's recipe is taken for it), `testing` (the model key is on
  the machine and the turns run, `Techtree.WalletBench.Turn`), `revoking` (the
  tests are over or one failed; the key comes off) and `done`, or `failed` with
  the reason. Every attempt that reached a machine goes through `revoking`:
  once the key is confirmed gone, the machine is reset for the next attempt;
  when it cannot be confirmed gone, the machine is deleted instead.

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
    RevokeCredentials
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
      accept [:harness_id, :wallet_id]
      validate one_of(:harness_id, Catalog.harness_ids())
      validate one_of(:wallet_id, Catalog.wallet_ids())
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
      constraints one_of: [:requested, :leased, :testing, :revoking, :done, :failed]
    end

    attribute :failure, :string, public?: true, description: "Why the attempt failed."

    timestamps()
  end

  relationships do
    belongs_to :machine, Machine, public?: true

    has_many :turns, Techtree.WalletBench.Turn do
      public? true
      sort inserted_at: :asc
    end
  end

  aggregates do
    sum :model_spend_usd, :turns, :model_spend_usd, public?: true
    sum :judge_cost_usd, :turns, :judge_cost_usd, public?: true
  end
end
