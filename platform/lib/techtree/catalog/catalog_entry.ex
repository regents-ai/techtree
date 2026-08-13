defmodule Techtree.Catalog.CatalogEntry do
  @moduledoc """
  One object the imported catalog ships, described well enough to find it.

  An entry is a searchable projection over a protocol object, never the object
  itself: where the exact bytes live inside the bundle, what they hash to, and —
  for a public Climb — the display fields and the summary map the catalog pages
  render. Serving a request still reads the bundle and hashes it again, so an
  entry can be wrong about a file but can never substitute for one.

  Entries outlive the release that imported them. An import marks everything it
  staged active and retires everything it did not, which keeps a digest that was
  once public resolvable as a historical row rather than deleting it.
  """

  use Ash.Resource,
    otp_app: :techtree,
    domain: Techtree.Catalog,
    data_layer: AshPostgres.DataLayer,
    authorizers: [Ash.Policy.Authorizer]

  postgres do
    table "catalog_entries"
    repo Techtree.Repo

    identity_wheres_to_sql unique_active_reference_per_kind: "active = true"
  end

  actions do
    defaults [:read]

    read :get_by_digest do
      description "Resolve one object by the digest it is filed under."
      get? true

      argument :protocol_digest, :string, allow_nil?: false

      filter expr(protocol_digest == ^arg(:protocol_digest))
    end

    read :get_by_reference do
      description "Resolve one object by its public reference within a kind."
      get? true

      argument :kind, :atom, allow_nil?: false
      argument :reference, :string, allow_nil?: false

      filter expr(kind == ^arg(:kind) and reference == ^arg(:reference))
    end

    read :list_active_climbs do
      description "The public Climbs the active release offers, in reference order."

      filter expr(kind == :climb and active == true)

      prepare build(sort: [reference: :asc])
    end

    create :upsert_from_import do
      description "Stage one object from a verified bundle. Import machinery only."

      accept [
        :protocol_digest,
        :kind,
        :reference,
        :relative_path,
        :media_type,
        :byte_size,
        :source_revision,
        :title,
        :summary,
        :status,
        :projection
      ]

      upsert? true
      upsert_identity :unique_protocol_digest

      upsert_fields [
        :kind,
        :reference,
        :relative_path,
        :media_type,
        :byte_size,
        :source_revision,
        :active,
        :title,
        :summary,
        :status,
        :projection
      ]

      change set_attribute(:active, true)
    end

    update :retire_missing_from_import do
      description "Retire an object the newly imported bundle no longer ships."
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

    attribute :protocol_digest, :string do
      description "The sha256 digest of the exact bytes this entry describes."
      allow_nil? false
      public? true
    end

    attribute :kind, :atom do
      description "What kind of protocol object the digest addresses."
      allow_nil? false
      public? true

      constraints one_of: [
                    :climb,
                    :campaign,
                    :data_policy,
                    :taskset_validation,
                    :validation_evidence
                  ]
    end

    attribute :reference, :string do
      description "The public `slug@version` reference, for objects that have one."
      public? true
    end

    attribute :relative_path, :string do
      description "Where the bytes live, relative to the catalog bundle root."
      allow_nil? false
      public? true
    end

    attribute :media_type, :string do
      description "The media type the exact bytes are served as."
      allow_nil? false
      public? true
    end

    attribute :byte_size, :integer do
      description "How many bytes the object is."
      allow_nil? false
      public? true
      constraints min: 0
    end

    attribute :source_revision, :string do
      description "The `techtree-python` revision the bundle was generated from."
      allow_nil? false
      public? true
    end

    attribute :active, :boolean do
      description "Whether the currently active release ships this object."
      allow_nil? false
      default true
      public? true
    end

    attribute :title, :string do
      description "The public title, for objects the catalog pages list."
      public? true
    end

    attribute :summary, :string do
      description "The public summary, for objects the catalog pages list."
      public? true
    end

    attribute :status, :string do
      description "The public status of a Climb: open, closed, or development."
      public? true
    end

    attribute :projection, :map do
      description "Display-only projection of the resolved object graph."
      allow_nil? false
      default %{}
      public? true
    end

    create_timestamp :inserted_at
    update_timestamp :updated_at
  end

  identities do
    identity :unique_protocol_digest, [:protocol_digest]

    # A retired entry keeps its reference so that history stays readable; the
    # constraint is that the *active* release offers each reference once.
    identity :unique_active_reference_per_kind, [:kind, :reference] do
      where expr(active == true)
    end
  end
end
