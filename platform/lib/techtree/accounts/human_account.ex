defmodule Techtree.Accounts.HumanAccount do
  @moduledoc "A person's shared Regent account, read from the table Regents owns."

  use Ash.Resource,
    domain: Techtree.Accounts,
    data_layer: AshPostgres.DataLayer,
    authorizers: [Ash.Policy.Authorizer],
    notifiers: [Ash.Notifier.PubSub]

  postgres do
    table "platform_human_users"
    schema "regent_names"
    repo Techtree.Repo
    migrate? false
  end

  actions do
    # Loading the name and picture after sign-in writes the account reads it
    # again through the primary read.
    read :read do
      primary? true
    end

    read :points_account do
      get? true
      argument :id, :integer, allow_nil?: false
      filter expr(id == ^arg(:id))
    end

    read :by_privy_did do
      get? true
      argument :privy_did, :string, allow_nil?: false
      filter expr(privy_user_id == ^arg(:privy_did))
      prepare build(load: [:display_name, :ens_name, :ens_avatar_url])
    end

    read :read_self do
      get? true
      argument :id, :integer, allow_nil?: false
      filter expr(id == ^arg(:id))
      prepare build(load: [:display_name, :ens_name, :ens_avatar_url])
    end

    create :register_verified do
      accept [:privy_user_id, :wallet_address, :wallet_addresses]
      upsert? true
      upsert_identity :unique_privy_user_id
      upsert_fields []
      change load([:display_name])
    end

    update :refresh_verified do
      accept [:wallet_address, :wallet_addresses]
      require_atomic? false
      validate present(:wallet_addresses)
      change load([:display_name, :ens_name, :ens_avatar_url])
    end
  end

  policies do
    policy action([
             :read,
             :by_privy_did,
             :register_verified,
             :refresh_verified,
             :points_account
           ]) do
      authorize_if actor_attribute_equals(:role, :system)
    end

    policy action(:read_self) do
      authorize_if expr(id == ^actor(:human_account_id))
    end
  end

  # A sign-in that changes or withdraws the account's wallets reaches the
  # account's open pages, which read the session again. Nothing about the
  # account travels with it.
  pub_sub do
    module Phoenix.PubSub
    name Techtree.PubSub
    prefix "human_account"
    broadcast_type :broadcast
    transform fn _notification -> nil end

    publish :refresh_verified, [:id]
  end

  attributes do
    integer_primary_key :id
    attribute :privy_user_id, :string, allow_nil?: false, sensitive?: true
    attribute :wallet_address, :string, sensitive?: true
    attribute :wallet_addresses, {:array, :string}, default: [], sensitive?: true
    attribute :avatar, :map
    create_timestamp :created_at
    update_timestamp :updated_at
  end

  relationships do
    has_one :ens_identity, Techtree.Accounts.EnsIdentity do
      destination_attribute :human_account_id
    end
  end

  calculations do
    # The name set in the person's shared Regent profile.
    calculate :display_name, :string, {RegentIdentity.ProfileName, otp_app: :techtree},
      public?: true

    # The ENS name and picture, only while they were read for the account's
    # current wallet.
    calculate :ens_name,
              :string,
              expr(
                if ens_identity.wallet_address == wallet_address do
                  ens_identity.ens_name
                end
              )

    calculate :ens_avatar_url,
              :string,
              expr(
                if ens_identity.wallet_address == wallet_address do
                  ens_identity.ens_avatar_url
                end
              )
  end

  @doc "The topic a sign-in's change to account `id` is published on."
  def topic(id), do: "human_account:#{id}"

  identities do
    identity :unique_privy_user_id, [:privy_user_id]
  end
end
