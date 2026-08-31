defmodule Techtree.Catalog do
  @moduledoc """
  The public catalog projection and the release state behind it.

  Ash holds what the site needs to *search and describe* — Climb summaries,
  which release is live, which bootstrap release is published. It does not hold
  the protocol objects themselves: those stay in the generated bundle as the
  exact bytes `techtree-python` produced (spec section 8.8), and are served from
  there after being hashed again. Keeping the two apart is what stops the
  website from becoming a second, subtly different scientific representation.

  Every write action here is import machinery. Public interfaces read; only the
  importer writes, and it does so with authorization explicitly bypassed.
  """

  use Ash.Domain, otp_app: :techtree

  @default_catalog_root {:priv, "catalog"}
  @default_channel "development"

  resources do
    resource Techtree.Catalog.CatalogEntry do
      define :list_catalog_entries, action: :read
      define :list_active_climbs, action: :list_active_climbs
      define :get_entry_by_digest, action: :get_by_digest, args: [:protocol_digest]
      define :get_entry_by_reference, action: :get_by_reference, args: [:kind, :reference]
      define :upsert_entry_from_import, action: :upsert_from_import
      define :retire_entries_missing_from_import, action: :retire_missing_from_import
    end

    resource Techtree.Catalog.CatalogRelease do
      define :list_catalog_releases, action: :read
      define :active_catalog_release, action: :active_release, args: [:channel]
      define :begin_catalog_import, action: :begin_import
      define :complete_catalog_import, action: :complete_import
      define :fail_catalog_import, action: :fail_import, args: [:error_summary]
      define :activate_catalog_release, action: :activate
      define :deactivate_catalog_release, action: :deactivate
    end

    resource Techtree.Catalog.BootstrapRelease do
      define :active_bootstrap_release, action: :active_release, args: [:channel]
      define :stage_bootstrap_release, action: :stage_from_import
      define :activate_bootstrap_release, action: :activate
      define :deactivate_bootstrap_release, action: :deactivate
    end
  end

  @doc """
  The directory holding the catalog bundle this build serves.

  Configured as `{:priv, subdirectory}` to name a directory shipped inside the
  release, or as a plain path to name a bundle deployed beside it.
  """
  @spec catalog_root() :: Path.t()
  def catalog_root do
    :techtree
    |> Application.get_env(__MODULE__, [])
    |> Keyword.get(:catalog_root, @default_catalog_root)
    |> case do
      {:priv, subdirectory} -> Application.app_dir(:techtree, ["priv", subdirectory])
      path when is_binary(path) -> path
    end
  end

  @doc """
  The release channel this build imports and serves.
  """
  @spec channel() :: String.t()
  def channel do
    :techtree
    |> Application.get_env(__MODULE__, [])
    |> Keyword.get(:channel, @default_channel)
  end
end
