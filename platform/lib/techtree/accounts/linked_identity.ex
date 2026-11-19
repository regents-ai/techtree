defmodule Techtree.Accounts.LinkedIdentity do
  @moduledoc """
  A social account Privy verified for one human account, one per provider.
  Several human accounts may link the same social account of a shared provider
  (`@shared_providers`); any other provider's social account is linked to one
  human account at a time.

  `inserted_at` is when this subject was linked to this account: a later
  sign-in with the same subject leaves it, and linking a different subject for
  the provider resets it. `verified_at` is Privy's newest check of the link.
  """

  use Ash.Resource,
    domain: Techtree.Accounts,
    data_layer: AshPostgres.DataLayer,
    authorizers: [Ash.Policy.Authorizer]

  # The providers whose social accounts several human accounts may link at once,
  # and the one place that choice is made. Every other provider's subject is held
  # by one account, which the database keeps to (`:unique_subject_per_provider`).
  @shared_providers [:x]

  postgres do
    table "linked_identities"
    repo Techtree.Repo

    identity_wheres_to_sql unique_subject_per_provider:
                             "provider NOT IN (#{Enum.map_join(@shared_providers, ", ", &"'#{&1}'")})"

    custom_indexes do
      # Points reads the links to one social account by its provider and subject,
      # shared or not. Built in the same short transaction as the subject rule.
      index [:provider, :subject]
    end
  end

  actions do
    create :upsert_verified do
      accept [
        :provider,
        :subject,
        :username,
        :display_name,
        :verified_at,
        :metadata,
        :human_account_id
      ]

      upsert? true
      upsert_identity :unique_provider_per_account
      # Reached only for a subject new to the account: a first link for the
      # provider, or one that replaces the account's earlier subject, so
      # `inserted_at` is always when this subject was linked.
      upsert_fields [:subject, :username, :display_name, :verified_at, :metadata, :inserted_at]

      emit Techtree.Accounts.Signals, :social_linked
    end

    # A sign-in that finds the same subject already linked to the account.
    update :refresh_verified do
      accept [:username, :display_name, :verified_at, :metadata]
      require_atomic? false
    end

    read :read_mine do
      filter expr(human_account_id == ^actor(:human_account_id))
      prepare build(sort: [provider: :asc])
    end

    read :for_account do
      argument :human_account_id, :integer, allow_nil?: false
      filter expr(human_account_id == ^arg(:human_account_id))
      prepare build(sort: [provider: :asc])
    end

    # Of the accounts that hold one social account, the link made first: the one
    # its Points answer for (`Techtree.Points.LinkedSocial`), so a later link by
    # another account moves nothing.
    read :first_link do
      get? true
      argument :provider, :atom, allow_nil?: false
      argument :subject, :string, allow_nil?: false
      filter expr(provider == ^arg(:provider) and subject == ^arg(:subject))
      prepare build(sort: [inserted_at: :asc, human_account_id: :asc], limit: 1)
    end

    # Each account's link to one provider made before a moment, such as the time the
    # Points start run reads them, by provider, subject and account alone, in
    # `:first_link`'s order.
    read :linked_before do
      argument :provider, :atom, allow_nil?: false
      argument :at, :utc_datetime_usec, allow_nil?: false
      filter expr(provider == ^arg(:provider) and inserted_at < ^arg(:at))

      prepare build(
                select: [:provider, :subject, :human_account_id],
                sort: [inserted_at: :asc, human_account_id: :asc]
              )
    end

    destroy :remove_verified do
      accept []
      require_atomic? false
    end
  end

  policies do
    policy action([
             :upsert_verified,
             :refresh_verified,
             :for_account,
             :first_link,
             :linked_before,
             :remove_verified
           ]) do
      authorize_if actor_attribute_equals(:role, :system)
    end

    policy action(:read_mine) do
      authorize_if actor_attribute_equals(:role, :human)
    end
  end

  attributes do
    uuid_primary_key :id

    attribute :provider, :atom,
      allow_nil?: false,
      public?: true,
      constraints: [one_of: [:x, :github, :farcaster]]

    attribute :subject, :string, allow_nil?: false
    attribute :username, :string, public?: true
    attribute :display_name, :string, public?: true
    attribute :verified_at, :utc_datetime_usec, allow_nil?: false, public?: true
    attribute :metadata, :map, allow_nil?: false, default: %{}
    timestamps()
  end

  relationships do
    belongs_to :human_account, Techtree.Accounts.HumanAccount do
      allow_nil? false
      attribute_type :integer
    end
  end

  identities do
    # One row per account and provider, so one per account and subject, shared
    # or not: sign-ins of one account at once meet in `:upsert_verified`, whose
    # conflict target this is.
    identity :unique_provider_per_account, [:provider, :human_account_id]

    # A sign-in reports the subject error as a social account another account
    # holds (`Techtree.Accounts.VerifiedSession`).
    identity :unique_subject_per_provider, [:provider, :subject] do
      where expr(provider not in ^@shared_providers)
      field_names [:subject]
    end
  end
end
