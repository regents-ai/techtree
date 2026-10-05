defmodule Techtree.WalletBench.Machine do
  @moduledoc """
  One Fly Sprites machine the bench owns, and the step it has reached.

  A machine serves one harness. `state` moves forward one step per job:
  `requested`, `created` (the machine exists on Sprites), `built` (the
  harness's baseline is installed, `Techtree.WalletBench.Machine.Changes.BuildBaseline`),
  `checkpointed` (its disk is saved as the baseline), `restored` (put back to
  the baseline), `settling` (its boot id is noted) and `ready`. An attempt
  takes a ready machine (`leased`) and gives it back for a reset (`resetting`),
  which goes through restore and readiness again. A machine whose build failed,
  whose boot id changed, whose upload did not come back exactly, whose image
  changed or whose tested account can reach the bench is `failed` at once, with
  the reason; a step that keeps failing to reach Sprites is `failed` when its
  retries run out. `retiring` asks for the machine to be deleted on Sprites;
  `retired` means it was.

  Each step calls Sprites before its transaction opens, then writes the new
  state, its `Techtree.WalletBench.MachineEvent` and the next step's job in one
  transaction, so a step that rolls back leaves no event and queues nothing. A
  step changes the machine only if it is still in the state the step follows, so
  a job that finishes after the machine was retired changes nothing.
  """

  use Ash.Resource,
    otp_app: :techtree,
    domain: Techtree.WalletBench,
    data_layer: AshPostgres.DataLayer,
    authorizers: [Ash.Policy.Authorizer],
    extensions: [AshOban]

  alias Techtree.WalletBench.Catalog

  alias Techtree.WalletBench.Machine.Changes.{
    BuildBaseline,
    CheckpointBaseline,
    ConfirmReady,
    CreateSprite,
    DeleteSprite,
    ObserveBoot,
    RecordEvent,
    RestoreBaseline
  }

  postgres do
    table "wallet_bench_machines"
    repo Techtree.Repo
  end

  oban do
    triggers do
      trigger :create_sprite do
        action :create_sprite
        where expr(state == :requested)
        queue(:sprites)
        max_attempts(5)
        on_error(:mark_failed)
        lock_for_update?(false)
        scheduler_cron(false)
        worker_module_name(Techtree.WalletBench.Machine.Workers.CreateSprite)
      end

      trigger :build_baseline do
        action :build_baseline
        where expr(state == :created)
        queue(:sprites)
        max_attempts(5)
        on_error(:mark_failed)
        lock_for_update?(false)
        scheduler_cron(false)
        worker_module_name(Techtree.WalletBench.Machine.Workers.BuildBaseline)
      end

      trigger :checkpoint_baseline do
        action :checkpoint_baseline
        where expr(state == :built)
        queue(:sprites)
        max_attempts(5)
        on_error(:mark_failed)
        lock_for_update?(false)
        scheduler_cron(false)
        worker_module_name(Techtree.WalletBench.Machine.Workers.CheckpointBaseline)
      end

      trigger :restore_baseline do
        action :restore_baseline
        where expr(state in [:checkpointed, :resetting])
        queue(:sprites)
        max_attempts(5)
        on_error(:mark_failed)
        lock_for_update?(false)
        scheduler_cron(false)
        worker_module_name(Techtree.WalletBench.Machine.Workers.RestoreBaseline)
      end

      trigger :observe_boot do
        action :observe_boot
        where expr(state == :restored)
        queue(:sprites)
        max_attempts(5)
        on_error(:mark_failed)
        lock_for_update?(false)
        scheduler_cron(false)
        worker_module_name(Techtree.WalletBench.Machine.Workers.ObserveBoot)
      end

      trigger :confirm_ready do
        action :confirm_ready
        where expr(state == :settling)
        queue(:sprites)
        max_attempts(5)
        on_error(:mark_failed)
        lock_for_update?(false)
        scheduler_cron(false)
        worker_module_name(Techtree.WalletBench.Machine.Workers.ConfirmReady)
      end

      trigger :delete_sprite do
        action :delete_sprite
        where expr(state == :retiring)
        queue(:sprites)
        max_attempts(5)
        on_error(:mark_failed)
        lock_for_update?(false)
        scheduler_cron(false)
        worker_module_name(Techtree.WalletBench.Machine.Workers.DeleteSprite)
      end
    end
  end

  actions do
    defaults [:read]

    create :request do
      description "Ask for a new machine for a harness; jobs take it from here. Operator only."
      accept [:name, :harness_id]
      validate one_of(:harness_id, Catalog.harness_ids())
      change set_attribute(:state, :requested)
      change RecordEvent
      change run_oban_trigger(:create_sprite)
    end

    update :create_sprite do
      require_atomic? false
      change filter(expr(state == :requested))
      change CreateSprite
      change set_attribute(:state, :created)
      change RecordEvent
      change run_oban_trigger(:build_baseline)
    end

    update :build_baseline do
      description "Built, or failed with the end of the build's log."
      require_atomic? false
      change filter(expr(state == :created))
      change BuildBaseline
      change RecordEvent
      change run_oban_trigger(:checkpoint_baseline)
    end

    update :checkpoint_baseline do
      require_atomic? false
      change filter(expr(state == :built))
      change CheckpointBaseline
      change set_attribute(:state, :checkpointed)
      change RecordEvent
      change run_oban_trigger(:restore_baseline)
    end

    update :restore_baseline do
      require_atomic? false
      change filter(expr(state in [:checkpointed, :resetting]))
      change RestoreBaseline
      change set_attribute(:state, :restored)
      change RecordEvent
      change run_oban_trigger(:observe_boot)
    end

    update :observe_boot do
      require_atomic? false
      change filter(expr(state == :restored))
      change ObserveBoot
      change set_attribute(:state, :settling)
      change RecordEvent
      change run_oban_trigger(:confirm_ready)
    end

    update :confirm_ready do
      description "Ready, or failed with the check that did not hold."
      require_atomic? false
      change filter(expr(state == :settling))
      change ConfirmReady
      change RecordEvent
    end

    update :lease do
      description "An attempt takes the ready machine. Attempt steps only."
      require_atomic? false
      argument :attempt_id, :uuid, allow_nil?: false
      change filter(expr(state == :ready))
      change set_attribute(:state, :leased)
      change {RecordEvent, argument: :attempt_id}
    end

    update :reset do
      description "The attempt is over and its key is gone; put the machine back. Attempt steps only."
      require_atomic? false
      argument :attempt_id, :uuid, allow_nil?: false
      change filter(expr(state == :leased))
      change set_attribute(:state, :resetting)
      change {RecordEvent, argument: :attempt_id}
      change run_oban_trigger(:restore_baseline)
    end

    update :mark_failed do
      description "A step ran out of retries."
      require_atomic? false
      argument :error, :term

      change filter(
               expr(
                 state in [
                   :requested,
                   :created,
                   :built,
                   :checkpointed,
                   :resetting,
                   :restored,
                   :settling,
                   :retiring
                 ]
               )
             )

      change set_attribute(:state, :failed)

      change fn changeset, _context ->
        message = changeset |> Ash.Changeset.get_argument(:error) |> describe_error()

        changeset
        |> Ash.Changeset.force_change_attribute(:failure, message)
        |> RecordEvent.put_detail(%{failure: message})
      end

      change RecordEvent
    end

    update :retire do
      description """
      Ask for the machine to be deleted on Sprites: by an operator, or by an
      attempt whose key could not be confirmed removed.
      """

      require_atomic? false
      argument :reason, :string, allow_nil?: false
      change filter(expr(state not in [:retiring, :retired]))
      change set_attribute(:state, :retiring)
      change {RecordEvent, argument: :reason}
      change run_oban_trigger(:delete_sprite)
    end

    update :delete_sprite do
      require_atomic? false
      change filter(expr(state == :retiring))
      change DeleteSprite
      change set_attribute(:state, :retired)
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

  attributes do
    uuid_primary_key :id

    attribute :name, :string do
      description "The machine's name on Sprites."
      allow_nil? false
      public? true
      constraints max_length: 63, match: ~r/\A[a-z0-9]+(?:-[a-z0-9]+)*\z/
    end

    attribute :state, :atom do
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

    attribute :harness_id, :string do
      description "The harness this machine's baseline holds."
      allow_nil? false
      public? true
    end

    attribute :recipe_digest, :string,
      public?: true,
      description: "The digest of the bench scripts the baseline carries."

    attribute :manifest, :map,
      public?: true,
      description: "The baseline's `manifest.json`: harness, translator, model and image facts."

    attribute :sprite_id, :string, public?: true
    attribute :sprite_version, :string, public?: true, description: "Sprites' image version."

    attribute :environment_version, :string,
      public?: true,
      description: "Sprites' environment image version; empty on some machines."

    attribute :baseline_checkpoint_id, :string, public?: true
    attribute :boot_id, :string, public?: true, description: "The boot id noted after restore."
    attribute :boot_seen_at, :utc_datetime_usec, public?: true
    attribute :failure, :string, public?: true, description: "Why the machine failed."

    timestamps()
  end

  identities do
    identity :unique_name, [:name]
  end

  @doc "A failed step's error, as one line."
  @spec describe_error(term()) :: String.t()
  def describe_error(error) when is_binary(error), do: String.slice(error, 0, 2000)

  def describe_error(%{__exception__: true} = error),
    do: error |> Exception.message() |> String.slice(0, 2000)

  def describe_error(error), do: error |> inspect() |> String.slice(0, 2000)
end
