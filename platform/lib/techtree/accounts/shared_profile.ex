defmodule Techtree.Accounts.SharedProfile do
  @moduledoc """
  The name in a person's shared Regent profile, read from the table
  `RegentIdentity.Profile` keeps, which this site edits only through `/profile`.
  Only `HumanAccount.ProfileName` reads it, unauthorized; no actor may.
  """

  use Ash.Resource,
    domain: Techtree.Accounts,
    data_layer: AshPostgres.DataLayer,
    authorizers: [Ash.Policy.Authorizer]

  postgres do
    table "profiles"
    schema "regent_identity"
    repo Techtree.Repo
    migrate? false
  end

  actions do
    defaults [:read]
  end

  policies do
    policy always() do
      forbid_if always()
    end
  end

  attributes do
    uuid_primary_key :id
    attribute :app_id, :string, allow_nil?: false, sensitive?: true
    attribute :privy_user_id, :string, allow_nil?: false, sensitive?: true
    attribute :display_name, :string
  end
end
