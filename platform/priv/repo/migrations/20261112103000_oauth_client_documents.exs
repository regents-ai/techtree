defmodule Techtree.Repo.Migrations.OAuthClientDocuments do
  @moduledoc """
  Published identities for connected apps, such as Claude's: an app that names
  itself by an HTTPS address is recorded as an ordinary client, and
  `RegentOAuth.Migration.V3` adds the one table that remembers which address
  each such client came from and when to read it again.

  Additive only: one new, empty table and its index, in this site's schema (its
  reference to `oauth_clients` names no schema of its own). Nothing existing
  changes.

  Hand-written; no resource changes shape. Up only, as the library's are.
  """

  use Ecto.Migration

  def up do
    execute "SET LOCAL lock_timeout = '5s'"

    RegentOAuth.Migration.V3.up()
  end
end
