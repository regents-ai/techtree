defmodule Techtree.Safety.Run do
  @moduledoc """
  One comparison of two monitors over one test pack, and every verdict it
  produced.

  The verdicts are one document column, appended to as cases finish, because
  the results page needs all of them or none of them and nothing ever asks for
  one verdict on its own. A run that was cancelled or failed keeps every
  verdict recorded before it stopped; its status says it is incomplete, and
  nothing here turns an incomplete run into a complete one.

  Runs on this site are public: every pack is synthetic and readable without
  signing in, and so is every run made from one. Only the runner writes, with
  authorization bypassed in the same explicit way the catalog importer does.
  """

  use Ash.Resource,
    otp_app: :techtree,
    domain: Techtree.Safety,
    data_layer: AshPostgres.DataLayer,
    authorizers: [Ash.Policy.Authorizer]

  postgres do
    table "safety_runs"
    repo Techtree.Repo
  end

  actions do
    defaults [:read]

    read :latest_complete do
      description "The most recent complete run of one pack, for the example link."
      get? true

      argument :test_slug, :string, allow_nil?: false

      filter expr(test_slug == ^arg(:test_slug) and status == :complete)
      prepare build(sort: [inserted_at: :desc], limit: 1)
    end

    read :started_since do
      description "Runs started at or after a moment, for the daily cap."

      argument :since, :utc_datetime_usec, allow_nil?: false

      filter expr(inserted_at >= ^arg(:since))
    end

    create :start do
      description "Record a comparison the moment it starts."
      accept [:test_slug, :test_version, :monitor_a, :monitor_b, :model, :case_count]
    end

    update :record_verdicts do
      description "Replace the verdict list with the one the runner now holds, while the run is still running."
      accept [:verdicts]
      require_atomic? false
      change filter(expr(status == :running))
    end

    update :finish do
      description "Close a running run with its final status. A closed run stays as it was closed."
      accept [:status, :failure]
      require_atomic? false
      change filter(expr(status == :running))
      change set_attribute(:finished_at, &DateTime.utc_now/0)
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

    attribute :test_slug, :string, allow_nil?: false, public?: true
    attribute :test_version, :integer, allow_nil?: false, public?: true
    attribute :monitor_a, :string, allow_nil?: false, public?: true
    attribute :monitor_b, :string, allow_nil?: false, public?: true
    attribute :model, :string, allow_nil?: false, public?: true
    attribute :case_count, :integer, allow_nil?: false, public?: true

    attribute :status, :atom do
      allow_nil? false
      public? true
      default :running
      constraints one_of: [:running, :complete, :cancelled, :failed]
    end

    attribute :verdicts, {:array, :map}, allow_nil?: false, default: [], public?: true
    attribute :failure, :string, public?: true

    create_timestamp :inserted_at
    attribute :finished_at, :utc_datetime_usec, public?: true
  end
end
