defmodule Techtree.WalletBench.Turn do
  @moduledoc """
  One prompt sent to the harness in an attempt, and what came of it.

  `state` moves forward one step per job: `queued`, `running` (the prompt is on
  the machine and the turn runs there as a background job), `finished` (the
  turn's folder is back, blanked and stored as evidence) and `judged`. A turn
  that cannot go on is `failed`, and its attempt stops. A turn never runs twice:
  an attempt has at most one turn per test, and the machine refuses to run a
  turn folder that already holds an exit code.

  Judging a turn decides what comes next (`Techtree.WalletBench.Turn.Changes.Advance`):
  T1b only when the judge named a technical error to send back, T2 only after an
  install worked, the signature request only when the agent signed but never
  printed the signature; otherwise the attempt's tests are over.

  A judged turn can be ruled on again (`:rejudge`) when the review guides
  change: the same stored evidence, a new ruling, and nothing after it runs.
  """

  use Ash.Resource,
    otp_app: :techtree,
    domain: Techtree.WalletBench,
    data_layer: AshPostgres.DataLayer,
    authorizers: [Ash.Policy.Authorizer],
    extensions: [AshOban],
    notifiers: [Ash.Notifier.PubSub]

  alias Techtree.WalletBench.Attempt.Changes.RecordEvent
  alias Techtree.WalletBench.{Catalog, Machine}
  alias Techtree.WalletBench.Turn.Changes.{Advance, CollectTurn, JudgeTurn, StartTurn}

  postgres do
    table "wallet_bench_turns"
    repo Techtree.Repo

    references do
      reference :attempt, on_delete: :nothing, on_update: :nothing
    end
  end

  oban do
    triggers do
      trigger :start do
        action :start
        where expr(state == :queued)
        queue(:sprites)
        max_attempts(5)
        on_error(:mark_failed)
        lock_for_update?(false)
        scheduler_cron(false)
        worker_module_name(Techtree.WalletBench.Turn.Workers.Start)
      end

      trigger :collect do
        action :collect
        where expr(state == :running)
        queue(:sprites)
        max_attempts(5)
        on_error(:mark_failed)
        lock_for_update?(false)
        scheduler_cron(false)
        worker_module_name(Techtree.WalletBench.Turn.Workers.Collect)
      end

      trigger :judge do
        action :judge
        where expr(state == :finished)
        queue(:wallet_bench_judge)
        max_attempts(5)
        on_error(:mark_failed)
        lock_for_update?(false)
        scheduler_cron(false)
        worker_module_name(Techtree.WalletBench.Turn.Workers.Judge)
      end
    end
  end

  actions do
    defaults [:read]

    create :queue do
      description "Queue one prompt for the harness. Attempt and turn steps only."
      accept [:attempt_id, :test, :prompt, :resume_session_id]
      change set_attribute(:state, :queued)
      change RecordEvent
      change run_oban_trigger(:start)
    end

    update :start do
      description "Puts the prompt on the machine and starts the turn there."
      require_atomic? false
      change filter(expr(state == :queued))
      change StartTurn
      change set_attribute(:state, :running)
      change RecordEvent
      change run_oban_trigger(:collect)
    end

    update :collect do
      description "Waits for the turn to end, then blanks and stores what it left; or failed."
      require_atomic? false
      change filter(expr(state == :running))
      change set_attribute(:state, :finished)
      change CollectTurn
      change RecordEvent
      change Advance
      change run_oban_trigger(:judge)
    end

    update :judge do
      description "The judge's ruling, then the next test or the end of the tests."
      require_atomic? false
      change filter(expr(state == :finished))
      change {JudgeTurn, evidence: :fresh}
      change set_attribute(:state, :judged)
      change RecordEvent
      change Advance
    end

    update :rejudge do
      description "A new ruling on a judged turn from its stored evidence; the attempt does not move."
      require_atomic? false
      change filter(expr(state == :judged))
      change {JudgeTurn, evidence: :stored}
      change RecordEvent
    end

    update :mark_failed do
      description "A step ran out of retries; the attempt stops."
      require_atomic? false
      argument :error, :term
      change filter(expr(state in [:queued, :running, :finished]))
      change set_attribute(:state, :failed)

      change fn changeset, _context ->
        message = changeset |> Ash.Changeset.get_argument(:error) |> Machine.describe_error()

        changeset
        |> Ash.Changeset.force_change_attribute(:failure, message)
        |> RecordEvent.put_detail(%{failure: message})
      end

      change RecordEvent
      change Advance
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
    publish_all :create, ["attempts", :attempt_id]
    publish_all :update, ["attempts", :attempt_id]
  end

  attributes do
    uuid_primary_key :id

    attribute :test, :atom do
      allow_nil? false
      public? true
      constraints one_of: Catalog.tests()
    end

    attribute :state, :atom do
      allow_nil? false
      public? true
      constraints one_of: [:queued, :running, :finished, :judged, :failed]
    end

    attribute :prompt, :string do
      description "The prompt as sent, word for word."
      allow_nil? false
      public? true
      constraints trim?: false, allow_empty?: false
    end

    attribute :resume_session_id, :string,
      public?: true,
      description: "The harness conversation this turn continues."

    attribute :session_id, :string, public?: true, description: "The harness conversation."
    attribute :exit_code, :integer, public?: true, description: "The harness's exit code."
    attribute :started_at, :utc_datetime_usec, public?: true
    attribute :ended_at, :utc_datetime_usec, public?: true
    attribute :wall_seconds, :decimal, public?: true

    attribute :model_spend_usd, :decimal,
      public?: true,
      description: "What the tested model's calls in this turn cost, as the translator counted."

    attribute :evidence, :map do
      description "Each stored file of the turn's folder, blanked: its sha256 and size."
      public? true
    end

    attribute :checks, :map do
      description "The bench's own checks for the judge, such as the Base check."
      public? true
    end

    attribute :judgment, :map do
      description "The judge's ruling: outcome, C1–C9, summary and reasoning."
      public? true
    end

    attribute :judge_cost_usd, :decimal do
      description "What every ruling on the turn cost together; each one's cost is also in the attempt's events."
      public? true
    end

    attribute :failure, :string, public?: true, description: "Why the turn failed."

    timestamps()
  end

  relationships do
    belongs_to :attempt, Techtree.WalletBench.Attempt do
      allow_nil? false
      public? true
    end
  end

  identities do
    identity :one_turn_per_test, [:attempt_id, :test]
  end
end
