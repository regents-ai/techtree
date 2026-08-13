defmodule Techtree.Catalog.BundleTest do
  use ExUnit.Case, async: true

  alias Techtree.Catalog.Bundle
  alias Techtree.Catalog.Error
  alias Techtree.CatalogFixture

  describe "load!/1" do
    test "reads the generated export as it was generated" do
      bundle = Bundle.load!(CatalogFixture.root())

      assert bundle.catalog["schema_version"] == "techtree.catalog.v1alpha1"
      assert bundle.bootstrap["channel"] == "development"
      assert Bundle.catalog_digest(bundle) == CatalogFixture.catalog_digest()
      assert Bundle.source_revision(bundle) == bundle.source["techtree_python_revision"]
      assert bundle.catalog_bytes == CatalogFixture.read!(CatalogFixture.root(), "catalog.json")
    end

    test "refuses a directory that is not a bundle", %{} do
      assert_raise Error, fn -> Bundle.load!("/nonexistent/catalog") end
    end

    @tag :tmp_dir
    test "refuses a bundle missing one of its three documents", %{tmp_dir: tmp_dir} do
      bundle = CatalogFixture.copy!(tmp_dir)
      File.rm!(Path.join(bundle, "bootstrap.json"))

      error = assert_raise Error, fn -> Bundle.load!(bundle) end
      assert error.code == :catalog_bundle_invalid
      assert error.details["path"] == "bootstrap.json"
    end
  end

  describe "list_entries/1" do
    test "lists every Climb and every content-addressed object" do
      entries = Bundle.list_entries(Bundle.load!(CatalogFixture.root()))

      assert Enum.map(entries, & &1.kind) == [
               :climb,
               :validation_evidence,
               :taskset_validation,
               :data_policy,
               :campaign
             ]

      climb = hd(entries)
      assert climb.reference == CatalogFixture.climb_reference()
      assert climb.relative_path == CatalogFixture.climb_path()
      assert climb.media_type == "application/json"
      assert Enum.all?(tl(entries), &is_nil(&1.reference))
    end
  end

  describe "read_object!/2" do
    test "returns the exact bytes the file holds" do
      bundle = Bundle.load!(CatalogFixture.root())

      assert Bundle.read_object!(bundle, CatalogFixture.campaign_digest()) ==
               CatalogFixture.read!(
                 CatalogFixture.root(),
                 "campaigns/hello-world-climb.json"
               )
    end

    test "refuses a digest the index does not file" do
      bundle = Bundle.load!(CatalogFixture.root())
      unknown = "sha256:" <> String.duplicate("b", 64)

      error = assert_raise Error, fn -> Bundle.read_object!(bundle, unknown) end
      assert error.code == :catalog_object_missing
    end

    @tag :tmp_dir
    test "refuses bytes that drifted from the digest they are filed under", %{tmp_dir: tmp_dir} do
      bundle = CatalogFixture.copy!(tmp_dir)
      CatalogFixture.write!(bundle, "campaigns/hello-world-climb.json", "{}")

      error =
        assert_raise Error, fn ->
          Bundle.read_object!(Bundle.load!(bundle), CatalogFixture.campaign_digest())
        end

      assert error.code == :catalog_object_digest_mismatch
      assert error.details["path"] == "campaigns/hello-world-climb.json"
    end
  end

  describe "resolve/2" do
    @tag :tmp_dir
    test "refuses absolute paths, traversal, and links out of the bundle", %{tmp_dir: tmp_dir} do
      bundle = CatalogFixture.copy!(tmp_dir)
      outside = Path.join(tmp_dir, "outside.json")
      File.write!(outside, "{}")
      File.ln_s!(outside, Path.join(bundle, "escape.json"))
      File.ln_s!(tmp_dir, Path.join(bundle, "up"))

      assert {:error, %Error{}} = Bundle.resolve(bundle, "/etc/passwd")
      assert {:error, %Error{}} = Bundle.resolve(bundle, "../outside.json")
      assert {:error, %Error{}} = Bundle.resolve(bundle, "climbs/../../outside.json")
      assert {:error, %Error{}} = Bundle.resolve(bundle, "escape.json")
      assert {:error, %Error{}} = Bundle.resolve(bundle, "up/outside.json")
      assert {:error, %Error{}} = Bundle.resolve(bundle, "climbs\\hello-world-climb.json")
      assert {:ok, _path} = Bundle.resolve(bundle, CatalogFixture.climb_path())
    end
  end
end
