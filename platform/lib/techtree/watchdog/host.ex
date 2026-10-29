defmodule Techtree.Watchdog.Host do
  @moduledoc """
  A site a person claims for Watchdog, by its bare host (`origin`). A host is
  `:verified` only once an automated check reads the proof the person published
  (`Techtree.Watchdog.Host.CheckOwnership`), in whichever way they chose
  (`ownership_method`): a DNS TXT record, or a file at a well-known address.
  A host that was proven and later stops publishing its proof drops to
  `:revoked` on its next check.

  Only the person who added a host reads or changes it, enforced by policy on
  `human_account_id`. Each check is run by an AshOban trigger so the request
  happens outside any transaction and retries on a hiccup; a daily sweep
  re-reads proven hosts so a withdrawn proof is noticed. The only request made
  about a host is the ownership check, which reaches nothing else of the site's.
  """

  use Ash.Resource,
    otp_app: :techtree,
    domain: Techtree.Watchdog,
    data_layer: AshPostgres.DataLayer,
    authorizers: [Ash.Policy.Authorizer],
    notifiers: [Ash.Notifier.PubSub],
    extensions: [AshOban]

  alias Techtree.Watchdog.EnforceCap
  alias Techtree.Watchdog.Host.{CheckOwnership, SetUp}

  postgres do
    table "watchdog_hosts"
    repo Techtree.Repo
  end

  oban do
    triggers do
      # The person's Verify press queues this; it reads the proof and records it.
      trigger :check_ownership do
        action :check_ownership
        where expr(ownership_state == :pending)
        queue(:watchdog)
        max_attempts(3)
        on_error(:check_failed)
        on_error_fails_job?(true)
        log_errors?(false)
        log_final_error?(false)
        lock_for_update?(false)
        scheduler_cron(false)
        worker_module_name(Techtree.Watchdog.Host.Workers.CheckOwnership)
      end

      # Once a day, re-read every proven host's proof, so a withdrawn proof is
      # noticed and the host drops to revoked.
      trigger :reverify do
        action :check_ownership
        where expr(ownership_state == :verified)
        queue(:watchdog)
        max_attempts(3)
        on_error(:check_failed)
        on_error_fails_job?(true)
        log_errors?(false)
        log_final_error?(false)
        lock_for_update?(false)
        scheduler_cron("41 3 * * *")
        worker_module_name(Techtree.Watchdog.Host.Workers.Reverify)
        scheduler_module_name(Techtree.Watchdog.Host.Schedulers.Reverify)
      end
    end
  end

  actions do
    defaults [:read]

    read :mine do
      prepare build(sort: [inserted_at: :asc], load: [:route_count])
    end

    create :add do
      accept [:ownership_method]
      argument :origin, :string, allow_nil?: false

      change SetUp

      change {EnforceCap,
              resource: __MODULE__,
              limit: :max_hosts_per_account,
              message: "You've reached the most sites we keep for one account."}
    end

    update :request_verification do
      change set_attribute(:ownership_state, :pending)
      change run_oban_trigger(:check_ownership)
    end

    update :check_ownership do
      transaction? false
      require_atomic? false
      change CheckOwnership
    end

    update :check_failed do
      change set_attribute(:ownership_state, :unverified)
    end

    destroy :remove
  end

  policies do
    bypass AshOban.Checks.AshObanInteraction do
      authorize_if always()
    end

    policy action_type([:read, :update, :destroy]) do
      authorize_if expr(human_account_id == ^actor(:human_account_id))
    end

    policy action(:add) do
      authorize_if actor_attribute_equals(:role, :human)
    end
  end

  # A finished check reaches the person's open Watchdog page, which reloads.
  pub_sub do
    module Phoenix.PubSub
    name Techtree.PubSub
    prefix "watchdog"
    broadcast_type :broadcast
    transform & &1.data

    publish :check_ownership, [:human_account_id]
    publish :check_failed, [:human_account_id]
  end

  attributes do
    uuid_primary_key :id

    attribute :origin, :string, allow_nil?: false, public?: true

    attribute :ownership_method, :atom,
      allow_nil?: false,
      public?: true,
      constraints: [one_of: [:dns_txt, :well_known_file]]

    attribute :verification_token, :string, allow_nil?: false

    attribute :ownership_state, :atom,
      allow_nil?: false,
      default: :unverified,
      public?: true,
      constraints: [one_of: [:unverified, :pending, :verified, :revoked]]

    attribute :verified_at, :utc_datetime, public?: true
    attribute :last_checked_at, :utc_datetime, public?: true

    create_timestamp :inserted_at, public?: true
    update_timestamp :updated_at, public?: true
  end

  relationships do
    belongs_to :human_account, Techtree.Accounts.HumanAccount do
      allow_nil? false
      attribute_type :integer
    end

    has_many :routes, Techtree.Watchdog.Route
  end

  aggregates do
    count :route_count, :routes do
      filter expr(state != :removed)
    end
  end

  identities do
    identity :unique_account_origin, [:human_account_id, :origin]
  end

  @doc "The topic a finished check for `human_account_id` is published on."
  def topic(human_account_id), do: "watchdog:#{human_account_id}"
end
