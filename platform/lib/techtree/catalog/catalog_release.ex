defmodule Techtree.Catalog.CatalogRelease do
  @moduledoc """
  One attempt to import a generated catalog bundle, and what came of it.

  A release is opened before any row is staged and closed after everything is,
  so a failure has somewhere to be recorded: the release that failed keeps the
  reason, and the release that was already active keeps serving. Exactly one
  release per channel is active at a time, enforced by a partial unique index
  rather than by convention.
  """

  use Ash.Resource,
    otp_app: :techtree,
    domain: Techtree.Catalog,
    data_layer: AshPostgres.DataLayer,
    authorizers: [Ash.Policy.Authorizer]

  postgres do
    table "catalog_releases"
    repo Techtree.Repo

    identity_wheres_to_sql one_active_release_per_channel: "active = true"
  end

  actions do
    defaults [:read]

    read :active_release do
      description "The completed release a channel currently serves."
      get? true

      argument :channel, :string, allow_nil?: false

      filter expr(channel == ^arg(:channel) and active == true and import_status == :complete)
    end

    create :begin_import do
      description "Open an import of a verified bundle. Import machinery only."

      accept [:channel, :catalog_digest, :source_revision, :bootstrap_digest]

      change set_attribute(:import_status, :importing)
      change set_attribute(:active, false)
    end

    update :complete_import do
      description "Record that every row of this import was staged."
      accept []

      change set_attribute(:import_status, :complete)
      change set_attribute(:imported_at, &DateTime.utc_now/0)
      change set_attribute(:error_summary, nil)
    end

    update :fail_import do
      description "Record why an import was rolled back."
      accept []

      argument :error_summary, :string, allow_nil?: false

      change set_attribute(:import_status, :failed)
      change set_attribute(:active, false)
      change set_attribute(:error_summary, arg(:error_summary))
    end

    update :activate do
      description "Serve this release on its channel."
      accept []

      change set_attribute(:active, true)
    end

    update :deactivate do
      description "Stop serving this release."
      accept []

      change set_attribute(:active, false)
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

    attribute :channel, :string do
      description "The release channel this import belongs to."
      allow_nil? false
      public? true
    end

    attribute :catalog_digest, :string do
      description "The digest of the exact catalog index bytes that were imported."
      allow_nil? false
      public? true
    end

    attribute :source_revision, :string do
      description "The `techtree-python` revision the bundle was generated from."
      allow_nil? false
      public? true
    end

    attribute :bootstrap_digest, :string do
      description "The digest of the exact bootstrap release bytes that were imported."
      allow_nil? false
      public? true
    end

    attribute :import_status, :atom do
      description "Where this import got to."
      allow_nil? false
      default :importing
      public? true
      constraints one_of: [:importing, :complete, :failed]
    end

    attribute :imported_at, :utc_datetime_usec do
      description "When the import completed."
      public? true
    end

    attribute :active, :boolean do
      description "Whether this release is the one being served on its channel."
      allow_nil? false
      default false
      public? true
    end

    attribute :error_summary, :string do
      description "A safe, sanitized reason a failed import was rolled back."
      public? true
    end

    create_timestamp :inserted_at
    update_timestamp :updated_at
  end

  identities do
    identity :one_active_release_per_channel, [:channel] do
      where expr(active == true)
    end
  end
end
