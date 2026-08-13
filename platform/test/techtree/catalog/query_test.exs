defmodule Techtree.Catalog.QueryTest do
  use Techtree.DataCase, async: false

  alias Techtree.Catalog.Error
  alias Techtree.Catalog.Importer
  alias Techtree.Catalog.Query
  alias Techtree.CatalogFixture

  describe "before anything is imported" do
    setup do
      CatalogFixture.use_bundle(CatalogFixture.root())
    end

    test "there is no release, and health says so plainly" do
      assert {:error, %Error{code: :bootstrap_release_missing}} = Query.active_catalog_release()
      assert {:error, %Error{code: :bootstrap_release_missing}} = Query.active_bootstrap_release()
      assert {:error, %Error{}} = Query.catalog_bytes()

      summary = Query.health_summary()

      assert summary.status == :unavailable
      assert summary.catalog_import_status == :none
      assert summary.channel == "development"
      refute Map.has_key?(summary, :source_revision)
    end
  end

  describe "once a release is active" do
    setup do
      CatalogFixture.use_bundle(CatalogFixture.root())
      %{release: Importer.import!(CatalogFixture.root())}
    end

    test "climbs are listed by reference" do
      assert [climb] = Query.list_climbs()
      assert climb.reference == CatalogFixture.climb_reference()
    end

    test "a bare slug resolves to the Climb it names" do
      assert {:ok, climb} = Query.get_climb_by_slug("procedure-transfer-dev")
      assert climb.reference == CatalogFixture.climb_reference()

      assert {:error, %Error{code: :catalog_object_missing}} =
               Query.get_climb_by_slug("no-such-climb")
    end

    test "an object is addressed only through the imported index" do
      digest = CatalogFixture.campaign_digest()

      assert {:ok, entry} = Query.get_entry_by_digest(digest)
      assert entry.relative_path == "campaigns/procedure-transfer-dev.json"

      assert {:error, %Error{code: :catalog_bundle_invalid}} =
               Query.get_entry_by_digest("../../etc/passwd")

      assert {:error, %Error{code: :catalog_bundle_invalid}} =
               Query.get_entry_by_digest(String.upcase(digest))

      assert {:error, %Error{code: :catalog_object_missing}} =
               Query.get_entry_by_digest("sha256:" <> String.duplicate("c", 64))
    end

    test "health reports the release being served and nothing about the host", %{
      release: release
    } do
      summary = Query.health_summary()

      assert summary.status == :ok
      assert summary.catalog_import_status == :complete
      assert summary.catalog_digest == release.catalog_digest
      assert summary.source_revision == release.source_revision
      assert summary.climb_count == 1

      refute summary |> inspect() |> String.contains?(CatalogFixture.root())
    end
  end

  describe "when the bundle drifts from the release that was imported" do
    @describetag :tmp_dir

    setup %{tmp_dir: tmp_dir} do
      bundle = CatalogFixture.copy!(tmp_dir)
      CatalogFixture.use_bundle(bundle)
      Importer.import!(bundle)

      %{bundle: bundle}
    end

    test "drifted bytes are refused rather than served", %{bundle: bundle} do
      CatalogFixture.write!(bundle, "campaigns/procedure-transfer-dev.json", "{}")

      assert {:error, %Error{code: :catalog_object_digest_mismatch}} =
               Query.object_bytes(CatalogFixture.campaign_digest())
    end

    test "a drifted index is refused rather than served", %{bundle: bundle} do
      CatalogFixture.write!(bundle, "catalog.json", "{}")

      assert {:error, %Error{code: :catalog_object_digest_mismatch}} = Query.catalog_bytes()
    end

    test "a removed object is reported as missing", %{bundle: bundle} do
      File.rm!(Path.join(bundle, "campaigns/procedure-transfer-dev.json"))

      assert {:error, %Error{code: :catalog_object_missing}} =
               Query.object_bytes(CatalogFixture.campaign_digest())
    end
  end
end
