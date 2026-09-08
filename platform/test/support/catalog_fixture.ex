defmodule Techtree.CatalogFixture do
  @moduledoc """
  The real generated catalog, and ways to damage a copy of it.

  `test/support/fixtures/catalog` is the `techtree.catalog.v2` export the CLI
  ships in `cli/src/techtree/resources/catalog`, copied byte for byte, plus the
  two documents a release adds beside it: the provenance record and the
  bootstrap release. Tests that need a valid bundle read it in place; tests
  that need a broken one copy it into the test's own temporary directory
  first, so no test can damage another's fixture.
  """

  alias Techtree.Catalog.Digest
  alias Techtree.Release.StarterSkill

  @climb_reference "hello-world-climb@1"
  @climb_path "climbs/hello-world-climb.json"
  @campaign_path "campaigns/hello-world-climb.json"
  @execution_plan_path "execution-plans/hello-world-climb.json"
  @campaign_digest "sha256:d5e91926076b69401c25c29868d00dad5c057ca4151a141b58186bb811b9f07c"
  @execution_plan_digest "sha256:6e3443231e0605c2a07b100507c72bd3c49fa848cf454f79f70666ab922f8eb3"
  @catalog_digest "sha256:edf773ee561c09413d9704046b2d53edff19bc04c0cfbe7d6efee646670a26f3"
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
  Rewrite the Campaign of a copied bundle, and refile everything that names it.

  A Campaign is addressed by its bytes, so a changed Campaign is a new digest:
  the index files it under that digest, and the Climb that points at it is
  rewritten to point at the new digest and refiled in turn. Every digest still
  matches its bytes afterwards, which is what lets a test reach the graph walk
  rather than stopping at an object that drifted.
  """
  @spec rewrite_campaign!(Path.t(), (map() -> map())) :: :ok
  def rewrite_campaign!(bundle, transform) do
    previous_digest = campaign_digest(bundle)
    campaign_digest = rewrite_object!(bundle, @campaign_path, transform)
    refile_object!(bundle, previous_digest, campaign_digest)

    climb_digest =
      rewrite_object!(bundle, @climb_path, &Map.put(&1, "campaign_spec_digest", campaign_digest))

    rewrite_index!(bundle, fn index ->
      Map.update!(index, "climbs", fn climbs ->
        Enum.map(climbs, fn climb ->
          if climb["path"] == @climb_path, do: Map.put(climb, "digest", climb_digest), else: climb
        end)
      end)
    end)
  end

  @doc """
  Rewrite the execution plan of a copied bundle, and refile the Campaign that
  binds it and the Climb above that, for the same reason.
  """
  @spec rewrite_execution_plan!(Path.t(), (map() -> map())) :: :ok
  def rewrite_execution_plan!(bundle, transform) do
    previous_digest = execution_plan_digest(bundle)
    plan_digest = rewrite_object!(bundle, @execution_plan_path, transform)
    refile_object!(bundle, previous_digest, plan_digest)
    rewrite_campaign!(bundle, &Map.put(&1, "execution_plan_digest", plan_digest))
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
  The digest of the resolved execution plan the fixture Campaign binds.
  """
  @spec execution_plan_digest() :: String.t()
  def execution_plan_digest, do: @execution_plan_digest

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

  # The digest a copied bundle currently files its Campaign or plan under: the
  # generated one until a rewrite moves it, and the moved one after.
  defp campaign_digest(bundle), do: Digest.hash_bytes(read!(bundle, @campaign_path))
  defp execution_plan_digest(bundle), do: Digest.hash_bytes(read!(bundle, @execution_plan_path))

  defp rewrite_object!(bundle, relative_path, transform) do
    bytes = bundle |> read!(relative_path) |> Jason.decode!() |> transform.() |> Jason.encode!()
    write!(bundle, relative_path, bytes)
    Digest.hash_bytes(bytes)
  end

  defp refile_object!(bundle, previous_digest, digest) do
    rewrite_index!(bundle, fn index ->
      Map.update!(index, "objects", fn objects ->
        {location, rest} = Map.pop!(objects, previous_digest)
        Map.put(rest, digest, location)
      end)
    end)
  end
end
