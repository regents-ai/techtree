defmodule Techtree.CatalogFixture do
  @moduledoc """
  The real generated catalog, and ways to damage a copy of it.

  `test/support/fixtures/catalog` is the export `techtree-python` ships, copied
  byte for byte, plus the two documents a release adds beside it: the
  provenance record and the bootstrap release. Tests that need a valid bundle
  read it in place; tests that need a broken one copy it into the test's own
  temporary directory first, so no test can damage another's fixture.
  """

  alias Techtree.Catalog.Digest

  @climb_reference "hello-world-climb@1"
  @climb_path "climbs/hello-world-climb.json"
  @campaign_digest "sha256:b65c1b0204dd2ceb1ec4c72a58c9888e6216c75d0eb40b7a11b18c85215a6b8b"
  @catalog_digest "sha256:91f7ba524194884bfd0556d4d47db1fc9c809e43081913cb15d4fd5b93abe0c8"

  @doc """
  The fixture bundle, as generated. Never write to this directory.
  """
  @spec root() :: Path.t()
  def root, do: Path.expand("fixtures/catalog", __DIR__)

  @doc """
  A writable copy of the fixture bundle inside `destination`.
  """
  @spec copy!(Path.t()) :: Path.t()
  def copy!(destination) do
    bundle = Path.join(destination, "catalog")
    File.mkdir_p!(bundle)
    File.cp_r!(root(), bundle)
    bundle
  end

  @doc """
  Serve and import from `bundle` for the duration of the calling test.
  """
  @spec use_bundle(Path.t()) :: :ok
  def use_bundle(bundle) do
    previous = Application.get_env(:techtree, Techtree.Catalog, [])

    Application.put_env(
      :techtree,
      Techtree.Catalog,
      Keyword.merge(previous, catalog_root: bundle)
    )

    ExUnit.Callbacks.on_exit(fn ->
      Application.put_env(:techtree, Techtree.Catalog, previous)
    end)

    :ok
  end

  @doc """
  Replace one file in a copied bundle.
  """
  @spec write!(Path.t(), String.t(), binary()) :: :ok
  def write!(bundle, relative_path, bytes) do
    path = Path.join(bundle, relative_path)
    File.mkdir_p!(Path.dirname(path))
    File.write!(path, bytes)
  end

  @doc """
  Read one file from a bundle.
  """
  @spec read!(Path.t(), String.t()) :: binary()
  def read!(bundle, relative_path), do: File.read!(Path.join(bundle, relative_path))

  @doc """
  Rewrite the catalog index of a copied bundle, keeping the provenance record
  truthful about the index that is now present.
  """
  @spec rewrite_index!(Path.t(), (map() -> map())) :: :ok
  def rewrite_index!(bundle, transform) do
    index =
      bundle
      |> read!("catalog.json")
      |> Jason.decode!()
      |> transform.()
      |> Jason.encode!()

    write!(bundle, "catalog.json", index)

    provenance =
      bundle
      |> read!("source.json")
      |> Jason.decode!()
      |> Map.put("catalog_digest", Digest.hash_bytes(index))
      |> Jason.encode!()

    write!(bundle, "source.json", provenance)
  end

  @doc """
  Rewrite the bootstrap release of a copied bundle.
  """
  @spec rewrite_bootstrap!(Path.t(), (map() -> map())) :: :ok
  def rewrite_bootstrap!(bundle, transform) do
    bootstrap =
      bundle
      |> read!("bootstrap.json")
      |> Jason.decode!()
      |> transform.()
      |> Jason.encode!()

    write!(bundle, "bootstrap.json", bootstrap)
  end

  @doc """
  The public reference of the Climb the fixture catalog ships.
  """
  @spec climb_reference() :: String.t()
  def climb_reference, do: @climb_reference

  @doc """
  Where the fixture Climb manifest lives inside the bundle.
  """
  @spec climb_path() :: String.t()
  def climb_path, do: @climb_path

  @doc """
  The digest of the fixture Climb manifest, as generated.
  """
  @spec climb_digest() :: String.t()
  def climb_digest do
    Digest.hash_bytes(read!(root(), @climb_path))
  end

  @doc """
  The digest of the CampaignSpec the fixture Climb points at.
  """
  @spec campaign_digest() :: String.t()
  def campaign_digest, do: @campaign_digest

  @doc """
  The digest of the fixture catalog index, as generated.
  """
  @spec catalog_digest() :: String.t()
  def catalog_digest, do: @catalog_digest
end
