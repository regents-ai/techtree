defmodule Techtree.Catalog.Query do
  @moduledoc """
  Everything the public surface is allowed to ask about the catalog.

  Controllers and LiveViews call this module and nothing else: they never build
  a query, and they never touch the filesystem. That is what keeps the two rules
  of the serving contract (spec section 8.6) in one place — a digest is resolved
  through the imported index rather than turned into a path, and exact bytes are
  hashed again before they are handed to anyone.
  """

  alias Techtree.Catalog
  alias Techtree.Catalog.Bundle
  alias Techtree.Catalog.CatalogEntry
  alias Techtree.Catalog.Digest
  alias Techtree.Catalog.Error

  @doc """
  The public Climbs the active release offers, in reference order.
  """
  @spec list_climbs(keyword()) :: [CatalogEntry.t()]
  def list_climbs(opts \\ []) do
    Catalog.list_active_climbs!(%{}, opts)
  end

  @doc """
  The highest active version of one Climb slug.

  A reader who did not name a version is asking for the current one, which is
  the same rule the CLI applies to a bare slug.
  """
  @spec get_climb_by_slug(String.t()) :: {:ok, CatalogEntry.t()} | {:error, Error.t()}
  def get_climb_by_slug(slug) when is_binary(slug) do
    list_climbs()
    |> Enum.filter(&(&1.projection["slug"] == slug))
    |> Enum.max_by(&version(&1.projection), fn -> nil end)
    |> case do
      nil ->
        {:error,
         Error.object_missing("this release ships no Climb by that name", %{"slug" => slug})}

      entry ->
        {:ok, entry}
    end
  end

  @doc """
  The catalog entry one digest addresses, whether or not it is still active.
  """
  @spec get_entry_by_digest(String.t()) :: {:ok, CatalogEntry.t()} | {:error, Error.t()}
  def get_entry_by_digest(digest) do
    with :ok <- check_digest(digest),
         {:ok, entry} when not is_nil(entry) <- Catalog.get_entry_by_digest(digest) do
      {:ok, entry}
    else
      {:error, %Error{} = error} ->
        {:error, error}

      _other ->
        {:error,
         Error.object_missing("this release ships no object under that digest", %{
           "digest" => digest
         })}
    end
  end

  @doc """
  The release currently being served, if there is one.
  """
  @spec active_catalog_release() :: {:ok, Catalog.CatalogRelease.t()} | {:error, Error.t()}
  def active_catalog_release do
    case Catalog.active_catalog_release(Catalog.channel()) do
      {:ok, nil} -> {:error, no_active_release()}
      {:ok, release} -> {:ok, release}
      {:error, _reason} -> {:error, no_active_release()}
    end
  end

  @doc """
  The bootstrap release currently being published, if there is one.
  """
  @spec active_bootstrap_release() :: {:ok, Catalog.BootstrapRelease.t()} | {:error, Error.t()}
  def active_bootstrap_release do
    case Catalog.active_bootstrap_release(Catalog.channel()) do
      {:ok, nil} -> {:error, no_active_bootstrap()}
      {:ok, release} -> {:ok, release}
      {:error, _reason} -> {:error, no_active_bootstrap()}
    end
  end

  @doc """
  The exact catalog index bytes of the active release, verified against the
  digest that release was imported under.
  """
  @spec catalog_bytes() :: {:ok, binary(), String.t()} | {:error, Error.t()}
  def catalog_bytes do
    with {:ok, release} <- active_catalog_release(),
         {:ok, bytes} <- read_file(Bundle.catalog_filename()) do
      verified(bytes, release.catalog_digest, Bundle.catalog_filename())
    end
  end

  @doc """
  The exact bytes of one content-addressed object, verified before returning,
  with the catalog entry that describes them.

  The digest is looked up in the imported index and only the stored
  catalog-relative path is resolved; a digest never becomes a path directly. The
  entry comes back with the bytes because the media type a response declares is
  the one the catalog recorded, not one inferred from the file.
  """
  @spec object_bytes(String.t()) :: {:ok, binary(), CatalogEntry.t()} | {:error, Error.t()}
  def object_bytes(digest) do
    with {:ok, _release} <- active_catalog_release(),
         {:ok, entry} <- get_entry_by_digest(digest),
         {:ok, bytes} <- read_file(entry.relative_path),
         {:ok, bytes, _digest} <- verified(bytes, entry.protocol_digest, entry.relative_path) do
      {:ok, bytes, entry}
    end
  end

  @doc """
  The exact bootstrap payload the active release publishes, verified against the
  digest it was imported under.
  """
  @spec bootstrap_payload() :: {:ok, binary(), String.t()} | {:error, Error.t()}
  def bootstrap_payload do
    with {:ok, release} <- active_bootstrap_release() do
      verified(release.raw_payload, release.payload_digest, "bootstrap.json")
    end
  end

  @doc """
  The published installation contract, read for display.

  The pages need the argument lists inside the payload, so the verified bytes
  are decoded here — for reading only. What the API serves is still the bytes,
  never this map, and no page ever runs any of it.
  """
  @spec bootstrap_instructions() :: {:ok, map()} | {:error, Error.t()}
  def bootstrap_instructions do
    with {:ok, instructions, _digest} <- bootstrap_instructions_with_digest() do
      {:ok, instructions}
    end
  end

  @doc """
  The published installation contract and the digest of those exact bytes.

  A page that displays both uses this form so a release cutover cannot pair one
  payload's instructions with another payload's digest.
  """
  @spec bootstrap_instructions_with_digest() ::
          {:ok, map(), String.t()} | {:error, Error.t()}
  def bootstrap_instructions_with_digest do
    with {:ok, payload, digest} <- bootstrap_payload() do
      case Jason.decode(payload) do
        {:ok, instructions} when is_map(instructions) ->
          {:ok, instructions, digest}

        _other ->
          {:error, Error.bundle_invalid("the published installation contract could not be read")}
      end
    end
  end

  @doc """
  Every object the active release ships, in a stable order.
  """
  @spec list_objects() :: [CatalogEntry.t()]
  def list_objects do
    Catalog.list_catalog_entries!(%{},
      query: [filter: [active: true], sort: [kind: :asc, reference: :asc]]
    )
  end

  @doc """
  What `/healthz` may say: whether a release is being served, and which one.

  It names no host path, no database, and no environment.
  """
  @spec health_summary() :: map()
  def health_summary do
    case active_catalog_release() do
      {:ok, release} ->
        %{
          status: :ok,
          channel: release.channel,
          catalog_import_status: release.import_status,
          catalog_digest: release.catalog_digest,
          source_revision: release.source_revision,
          imported_at: release.imported_at,
          climb_count: length(list_climbs())
        }

      {:error, %Error{code: code}} ->
        %{
          status: :unavailable,
          channel: Catalog.channel(),
          catalog_import_status: :none,
          reason: code
        }
    end
  end

  defp verified(bytes, digest, relative_path) do
    case Digest.verify_bytes(bytes, digest) do
      :ok ->
        {:ok, bytes, digest}

      {:error, computed} ->
        {:error,
         Error.object_digest_mismatch(
           "the served bytes do not match the digest they are filed under",
           %{
             "path" => relative_path,
             "expected_digest" => digest,
             "computed_digest" => computed
           }
         )}
    end
  end

  defp read_file(relative_path) do
    with {:ok, path} <- Bundle.resolve(Catalog.catalog_root(), relative_path) do
      case File.read(path) do
        {:ok, bytes} ->
          {:ok, bytes}

        {:error, reason} ->
          {:error,
           Error.object_missing("the active release does not ship this object", %{
             "path" => relative_path,
             "reason" => to_string(:file.format_error(reason))
           })}
      end
    end
  end

  defp check_digest(digest) do
    if Digest.valid?(digest) do
      :ok
    else
      {:error,
       Error.bundle_invalid("a digest is spelled sha256: followed by 64 lowercase hex characters")}
    end
  end

  defp version(%{"version" => version}) when is_integer(version), do: version
  defp version(_projection), do: 0

  defp no_active_release do
    Error.bootstrap_missing("no catalog release is active on this channel", %{
      "channel" => Catalog.channel()
    })
  end

  defp no_active_bootstrap do
    Error.bootstrap_missing("no bootstrap release is published on this channel", %{
      "channel" => Catalog.channel()
    })
  end
end
