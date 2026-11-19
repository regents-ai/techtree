defmodule Techtree.Repo.Migrations.SharedXAccounts do
  @moduledoc """
  Several accounts may link the same X account (`Techtree.Accounts.LinkedIdentity`
  `@shared_providers`): the rule that one account holds a provider's subject now
  leaves X out and still holds for GitHub and Farcaster. Its index is replaced, in
  one transaction, by the same index over every row but X's, so no moment passes
  without the rule. A plain index on provider and subject serves Points' read of the
  links to one social account. No row changes. The table is in the site's own
  schema, which is the prefix the migration runs with.

  Locks: dropping the index takes `ACCESS EXCLUSIVE` on `linked_identities`, held
  until commit across both index builds, so the table's reads and writes wait for
  the transaction. The table holds one row per account per linked provider. The
  lock is waited for at most 5 seconds; past that the release command fails and
  nothing changes.

  `down` brings back the rule for every provider, X included; it fails, changing
  nothing, while two accounts hold the same X account.

  Generated with `mix ash.codegen shared_x_accounts`.
  """

  use Ecto.Migration

  def up do
    execute("SET LOCAL lock_timeout = '5s'")

    drop_if_exists unique_index(:linked_identities, [:provider, :subject],
                     name: "linked_identities_unique_subject_per_provider_index"
                   )

    create unique_index(:linked_identities, [:provider, :subject],
             name: "linked_identities_unique_subject_per_provider_index",
             where: "(provider NOT IN ('x'))"
           )

    create index(:linked_identities, [:provider, :subject])
  end

  def down do
    execute("SET LOCAL lock_timeout = '5s'")

    drop_if_exists index(:linked_identities, [:provider, :subject])

    drop_if_exists unique_index(:linked_identities, [:provider, :subject],
                     name: "linked_identities_unique_subject_per_provider_index"
                   )

    create unique_index(:linked_identities, [:provider, :subject],
             name: "linked_identities_unique_subject_per_provider_index"
           )
  end
end
