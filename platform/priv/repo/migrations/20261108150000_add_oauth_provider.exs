defmodule Techtree.Repo.Migrations.AddOAuthProvider do
  @moduledoc """
  The Claude connector's sign-in tables, `oauth_*` in this site's schema, at
  the provider's current version: `RegentOAuth.Migration` creates them and
  `RegentOAuth.Migration.V2` keeps only the hash of each access and refresh
  token. The tables are new, so V2 has no row to rewrite; it runs here so the
  schema is the version the library reads. Only adds tables; nothing existing
  changes.

  Neither needs the site's address: each code and token gets this site's
  issuer and resource written on it as it is issued, and one whose values
  differ from the running site's is refused.

  Hand-written; no resource changes shape. Up only, as the library's are.
  """

  use Ecto.Migration

  def up do
    execute "SET LOCAL lock_timeout = '5s'"

    RegentOAuth.Migration.up()
    RegentOAuth.Migration.V2.up()
  end
end
