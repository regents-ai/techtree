defmodule Techtree.Watchdog.Route do
  @moduledoc """
  One address on a host a person has claimed. In this slice a route is always a
  public address (`kind`); addresses behind a login wait for the gated part of
  Watchdog. A route is `:active`, `:paused` by its owner, or `:removed`. It can
  be `:active` only under a proven host, so a route under a host that is not yet
  proven cannot be tested.

  Only the person who added a route reads or changes it, enforced by policy on
  `human_account_id`.
  """

  use Ash.Resource,
    otp_app: :techtree,
    domain: Techtree.Watchdog,
    data_layer: AshPostgres.DataLayer,
    authorizers: [Ash.Policy.Authorizer]

  alias Techtree.Watchdog.EnforceCap
  alias Techtree.Watchdog.Route.Attach

  postgres do
    table "watchdog_routes"
    repo Techtree.Repo

    references do
      reference :host, on_delete: :delete
    end
  end

  actions do
    defaults [:read]

    read :mine do
      prepare build(sort: [inserted_at: :asc])
    end

    create :add do
      accept [:url]
      argument :host_id, :uuid, allow_nil?: false

      change Attach

      change {EnforceCap,
              resource: __MODULE__,
              limit: :max_routes_per_account,
              message: "You've reached the most addresses we keep for one account."}
    end

    update :pause do
      change set_attribute(:state, :paused)
    end

    update :resume do
      require_atomic? false
      validate attribute_equals(:state, :paused)
      change Techtree.Watchdog.Route.Resume
    end

    destroy :remove
  end

  policies do
    policy action_type([:read, :update, :destroy]) do
      authorize_if expr(human_account_id == ^actor(:human_account_id))
    end

    policy action(:add) do
      authorize_if actor_attribute_equals(:role, :human)
    end
  end

  attributes do
    uuid_primary_key :id

    attribute :url, :string, allow_nil?: false, public?: true

    attribute :kind, :atom,
      allow_nil?: false,
      default: :public,
      public?: true,
      constraints: [one_of: [:public]]

    attribute :state, :atom,
      allow_nil?: false,
      default: :active,
      public?: true,
      constraints: [one_of: [:active, :paused, :removed]]

    create_timestamp :inserted_at, public?: true
    update_timestamp :updated_at, public?: true
  end

  relationships do
    belongs_to :host, Techtree.Watchdog.Host do
      allow_nil? false
    end

    belongs_to :human_account, Techtree.Accounts.HumanAccount do
      allow_nil? false
      attribute_type :integer
    end
  end
end
