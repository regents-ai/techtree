defmodule Techtree.Catalog.BootstrapRelease do
  @moduledoc """
  The published installation contract for one channel, kept as exact bytes.

  Unlike the protocol objects, the bootstrap release is small, mutable between
  releases, and requested by tooling that must be able to check it did not
  change under them — so the payload is stored here rather than read from the
  bundle at request time, and it is stored as the bytes that were verified, not
  as a decoded map. The API re-hashes `raw_payload` against `payload_digest`
  before serving it.

  The indexed columns beside the payload exist so that a page can say which CLI
  version and which pinned plugin commit are current without parsing the
  payload. They are descriptions of the bytes, never a substitute for them.
  """

  use Ash.Resource,
    otp_app: :techtree,
    domain: Techtree.Catalog,
    data_layer: AshPostgres.DataLayer,
    authorizers: [Ash.Policy.Authorizer]

  postgres do
    table "bootstrap_releases"
    repo Techtree.Repo

    identity_wheres_to_sql one_active_bootstrap_per_channel: "active = true"
  end

  actions do
    defaults [:read]

    read :active_release do
      description "The bootstrap release a channel currently publishes."
      get? true

      argument :channel, :string, allow_nil?: false

      filter expr(channel == ^arg(:channel) and active == true)
    end

    create :stage_from_import do
      description "Stage the exact bootstrap payload of a verified bundle."

      accept [
        :channel,
        :schema_version,
        :raw_payload,
        :payload_digest,
        :cli_version,
        :plugin_revision,
        :minimum_hermes_version,
        :published_at
      ]

      upsert? true
      upsert_identity :unique_payload_per_channel

      upsert_fields [
        :schema_version,
        :raw_payload,
        :cli_version,
        :plugin_revision,
        :minimum_hermes_version,
        :published_at,
        :active
      ]

      change set_attribute(:active, false)
    end

    update :activate do
      description "Publish this bootstrap release on its channel."
      accept []

      change set_attribute(:active, true)
    end

    update :deactivate do
      description "Stop publishing this bootstrap release."
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
      description "The release channel this bootstrap contract belongs to."
      allow_nil? false
      public? true
    end

    attribute :schema_version, :string do
      description "The protocol schema version of the payload."
      allow_nil? false
      public? true
    end

    attribute :raw_payload, :binary do
      description "The exact bytes served by the bootstrap endpoint."
      allow_nil? false
      public? true
    end

    attribute :payload_digest, :string do
      description "The sha256 digest of `raw_payload`, checked before serving."
      allow_nil? false
      public? true
    end

    attribute :cli_version, :string do
      description "The exact CLI version this release pins."
      allow_nil? false
      public? true
    end

    attribute :plugin_revision, :string do
      description "The immutable Hermes plugin commit this release pins."
      allow_nil? false
      public? true
    end

    attribute :minimum_hermes_version, :string do
      description "The lowest host Hermes version this release supports."
      allow_nil? false
      public? true
    end

    attribute :published_at, :utc_datetime_usec do
      description "When this bootstrap release was published."
      allow_nil? false
      public? true
    end

    attribute :active, :boolean do
      description "Whether this is the bootstrap release the channel publishes."
      allow_nil? false
      default false
      public? true
    end

    create_timestamp :inserted_at
    update_timestamp :updated_at
  end

  identities do
    identity :unique_payload_per_channel, [:channel, :payload_digest]

    identity :one_active_bootstrap_per_channel, [:channel] do
      where expr(active == true)
    end
  end
end
