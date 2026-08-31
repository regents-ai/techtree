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
  alias Techtree.Release.StarterSkill

  @climb_reference "hello-world-climb@1"
  @climb_path "climbs/hello-world-climb.json"
  @campaign_digest "sha256:ebf029abb266ca74c2def50eb23030511bab0e929c6bf4a68691f9b5afd554b1"
  @catalog_digest "sha256:10a7fcc5de1951c14509947c0512a4eeb247a703cdf01cc3f268580979a7d12c"
  @taskset_validation_digest "sha256:4944bd71caa1a295e03325b18a7af753d0d8fcf787189c89244209171cda1302"
  @data_policy_digest "sha256:6c532a43d595286a08260481890bbbffa16d1b4dd89465d1cc8395099d9ebcf9"

  # Stand-ins with the shape of a real coordinate and none of its meaning.
  @commit String.duplicate("a", 40)
  @object_url "https://techtree.test/api/v1/objects/" <> StarterSkill.file_digest()

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
  The fixture bootstrap release, rewritten as a release that claims every
  coordinate is real.

  These are test values, not release coordinates: what they are for is to make
  a document that passes decision 0007 R10, so that a test can spoil exactly one
  field of it and watch the import refuse.
  """
  @spec concrete_release(map()) :: map()
  def concrete_release(bootstrap) do
    bootstrap
    |> Map.put("placeholder_release", false)
    |> put_in(["cli", "version"], "0.1.0")
    |> put_in(["cli", "source_revision"], @commit)
    |> put_in(["cli", "install_argv"], [
      "uv",
      "tool",
      "install",
      "--python",
      "3.12",
      "techtree==0.1.0"
    ])
    |> put_in(["hermes_plugin", "revision"], @commit)
    |> put_in(["hermes_plugin", "install_argv"], [
      "hermes",
      "plugins",
      "install",
      "regents-ai/techtree-hermes",
      "--ref",
      @commit,
      "--enable"
    ])
    |> put_in(["starter_skill", "object_url"], @object_url)
    |> put_in(["starter_skill", "file_digest"], StarterSkill.file_digest())
    |> put_in(["starter_skill", "tree_digest"], StarterSkill.tree_digest())
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

  @doc """
  The publisher's signed task-validation receipt, and the data policy.

  Written out here rather than hashed from the fixture, for the same reason
  the campaign digest is: a test that recomputes the number it is checking
  cannot notice the fixture changing underneath it. When the science moves
  these move with it, by hand, which is the point.
  """
  @spec taskset_validation_digest() :: String.t()
  def taskset_validation_digest, do: @taskset_validation_digest

  @spec data_policy_digest() :: String.t()
  def data_policy_digest, do: @data_policy_digest
end
