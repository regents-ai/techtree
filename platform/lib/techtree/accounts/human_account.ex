defmodule Techtree.Accounts.HumanAccount do
  @moduledoc "Read-only canonical account projection; Regents owns this table."
  use Ash.Resource,
    domain: Techtree.Accounts,
    data_layer: AshPostgres.DataLayer,
    authorizers: [Ash.Policy.Authorizer]

  postgres do
    table "platform_human_users"
    schema "regent_names"
    repo Techtree.Repo
    migrate? false
  end

  actions do
    defaults [:read]

    read :by_owner do
      get? true
      argument :owner, :string, allow_nil?: false
      filter expr(privy_user_id == ^arg(:owner))
    end

    read :by_id do
      get? true
      argument :id, :integer, allow_nil?: false
      filter expr(id == ^arg(:id))
    end
  end

  policies do
    policy action_type(:read) do
      authorize_if actor_attribute_equals(:role, :system)
    end
  end

  attributes do
    integer_primary_key :id
    attribute :privy_user_id, :string, allow_nil?: false, sensitive?: true
    attribute :wallet_address, :string, sensitive?: true
    attribute :wallet_addresses, {:array, :string}, default: [], sensitive?: true
  end
end
