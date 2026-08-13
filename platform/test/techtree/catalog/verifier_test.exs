defmodule Techtree.Catalog.VerifierTest do
  use ExUnit.Case, async: true

  alias Techtree.Catalog.Bundle
  alias Techtree.Catalog.Error
  alias Techtree.Catalog.Verifier
  alias Techtree.CatalogFixture

  test "the generated catalog verifies as generated" do
    assert :ok == Verifier.verify_bundle(Bundle.load!(CatalogFixture.root()))
  end

  describe "object bytes" do
    @tag :tmp_dir
    test "a mutated object is rejected", %{tmp_dir: tmp_dir} do
      bundle = CatalogFixture.copy!(tmp_dir)
      original = CatalogFixture.read!(bundle, "data-policies/procedure-transfer-dev.json")
      CatalogFixture.write!(bundle, "data-policies/procedure-transfer-dev.json", original <> " ")

      assert {:error, error} = verify(bundle)
      assert error.code == :catalog_object_digest_mismatch
    end

    @tag :tmp_dir
    test "a missing object is rejected", %{tmp_dir: tmp_dir} do
      bundle = CatalogFixture.copy!(tmp_dir)
      File.rm!(Path.join(bundle, "validation-evidence/procedure-transfer-dev.json"))

      assert {:error, error} = verify(bundle)
      assert error.code == :catalog_object_missing
      assert error.details["path"] == "validation-evidence/procedure-transfer-dev.json"
    end
  end

  describe "the catalog index" do
    @tag :tmp_dir
    test "an index the provenance does not describe is rejected", %{tmp_dir: tmp_dir} do
      bundle = CatalogFixture.copy!(tmp_dir)
      index = CatalogFixture.read!(bundle, "catalog.json")
      CatalogFixture.write!(bundle, "catalog.json", index <> "\n")

      assert {:error, error} = verify(bundle)
      assert error.code == :catalog_object_digest_mismatch
      assert error.details["expected_digest"] == CatalogFixture.catalog_digest()
    end

    @tag :tmp_dir
    test "an unsupported schema version is rejected", %{tmp_dir: tmp_dir} do
      bundle = CatalogFixture.copy!(tmp_dir)

      CatalogFixture.rewrite_index!(bundle, &Map.put(&1, "schema_version", "techtree.catalog.v2"))

      assert {:error, error} = verify(bundle)
      assert error.code == :catalog_bundle_invalid
    end

    @tag :tmp_dir
    test "an uppercase digest is rejected", %{tmp_dir: tmp_dir} do
      bundle = CatalogFixture.copy!(tmp_dir)

      CatalogFixture.rewrite_index!(bundle, fn index ->
        Map.update!(index, "climbs", fn [climb | rest] ->
          [Map.update!(climb, "digest", &String.upcase/1) | rest]
        end)
      end)

      assert {:error, error} = verify(bundle)
      assert error.code == :catalog_bundle_invalid
      assert error.message =~ "sha256 digest"
    end

    @tag :tmp_dir
    test "an unknown object kind is rejected", %{tmp_dir: tmp_dir} do
      bundle = CatalogFixture.copy!(tmp_dir)

      CatalogFixture.rewrite_index!(bundle, fn index ->
        Map.update!(index, "objects", fn objects ->
          Map.new(objects, fn {digest, location} ->
            {digest, Map.put(location, "kind", "episode_receipt")}
          end)
        end)
      end)

      assert {:error, error} = verify(bundle)
      assert error.code == :catalog_bundle_invalid
      assert error.message =~ "unknown kind"
    end

    @tag :tmp_dir
    test "a path that leaves the bundle is rejected", %{tmp_dir: tmp_dir} do
      bundle = CatalogFixture.copy!(tmp_dir)
      File.write!(Path.join(tmp_dir, "outside.json"), "{}")

      CatalogFixture.rewrite_index!(bundle, fn index ->
        Map.update!(index, "climbs", fn [climb | rest] ->
          [Map.put(climb, "path", "../outside.json") | rest]
        end)
      end)

      assert {:error, error} = verify(bundle)
      assert error.code == :catalog_bundle_invalid
      assert error.details["path"] == "../outside.json"
    end

    @tag :tmp_dir
    test "a dangling reference is rejected", %{tmp_dir: tmp_dir} do
      bundle = CatalogFixture.copy!(tmp_dir)

      CatalogFixture.rewrite_index!(bundle, fn index ->
        Map.update!(index, "objects", &Map.delete(&1, CatalogFixture.campaign_digest()))
      end)

      File.rm!(Path.join(bundle, "campaigns/procedure-transfer-dev.json"))

      assert {:error, error} = verify(bundle)
      assert error.code == :catalog_object_missing
      assert error.details["digest"] == CatalogFixture.campaign_digest()
    end
  end

  describe "the bootstrap release" do
    @tag :tmp_dir
    test "an install instruction that is not an argument array is rejected", %{tmp_dir: tmp_dir} do
      bundle = CatalogFixture.copy!(tmp_dir)

      CatalogFixture.rewrite_bootstrap!(bundle, fn bootstrap ->
        put_in(bootstrap, ["cli", "install_argv"], "uv tool install techtree==0.1.0")
      end)

      assert {:error, error} = verify(bundle)
      assert error.code == :catalog_bundle_invalid
      assert error.details["field"] == "cli.install_argv"
    end

    @tag :tmp_dir
    test "a plugin revision that is not a full commit is rejected", %{tmp_dir: tmp_dir} do
      bundle = CatalogFixture.copy!(tmp_dir)

      CatalogFixture.rewrite_bootstrap!(bundle, fn bootstrap ->
        put_in(bootstrap, ["hermes_plugin", "revision"], "main")
      end)

      assert {:error, error} = verify(bundle)
      assert error.details["field"] == "hermes_plugin.revision"
    end

    @tag :tmp_dir
    test "an introductory Climb this catalog does not ship is rejected", %{tmp_dir: tmp_dir} do
      bundle = CatalogFixture.copy!(tmp_dir)

      CatalogFixture.rewrite_bootstrap!(bundle, fn bootstrap ->
        put_in(bootstrap, ["introductory_climb", "reference"], "something-else@1")
      end)

      assert {:error, error} = verify(bundle)
      assert error.code == :catalog_object_missing
      assert error.details["reference"] == "something-else@1"
    end
  end

  defp verify(bundle) do
    case Verifier.verify_bundle(Bundle.load!(bundle)) do
      :ok -> :ok
      {:error, %Error{} = error} -> {:error, error}
    end
  end
end
