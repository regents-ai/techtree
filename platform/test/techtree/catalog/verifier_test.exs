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
      original = CatalogFixture.read!(bundle, "data-policies/hello-world-climb.json")
      CatalogFixture.write!(bundle, "data-policies/hello-world-climb.json", original <> " ")

      assert {:error, error} = verify(bundle)
      assert error.code == :catalog_object_digest_mismatch
    end

    @tag :tmp_dir
    test "a missing object is rejected", %{tmp_dir: tmp_dir} do
      bundle = CatalogFixture.copy!(tmp_dir)
      File.rm!(Path.join(bundle, "validation-evidence/hello-world-climb.json"))

      assert {:error, error} = verify(bundle)
      assert error.code == :catalog_object_missing
      assert error.details["path"] == "validation-evidence/hello-world-climb.json"
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

      File.rm!(Path.join(bundle, "campaigns/hello-world-climb.json"))

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

    @tag :tmp_dir
    test "a bundle that names no starter Skill at all is rejected", %{tmp_dir: tmp_dir} do
      bundle = CatalogFixture.copy!(tmp_dir)

      CatalogFixture.rewrite_bootstrap!(bundle, &Map.delete(&1, "starter_skill"))

      assert {:error, error} = verify(bundle)
      assert error.code == :catalog_bundle_invalid
      assert error.details["field"] == "starter_skill.object_url"
    end

    @tag :tmp_dir
    test "a starter Skill address a machine cannot fetch from is rejected",
         %{tmp_dir: tmp_dir} do
      for address <- [
            "http://example.com/skill.md",
            "https://token@example.com/skill.md",
            "https://example.com",
            "not a url",
            ""
          ] do
        bundle = CatalogFixture.copy!(Path.join(tmp_dir, Base.url_encode64(address)))

        CatalogFixture.rewrite_bootstrap!(bundle, fn bootstrap ->
          put_in(bootstrap, ["starter_skill", "object_url"], address)
        end)

        assert {:error, error} = verify(bundle), "#{inspect(address)} was accepted"
        assert error.details["field"] == "starter_skill.object_url"
      end
    end

    @tag :tmp_dir
    test "a starter Skill digest that is not a sha256 digest is rejected", %{tmp_dir: tmp_dir} do
      bundle = CatalogFixture.copy!(tmp_dir)

      CatalogFixture.rewrite_bootstrap!(bundle, fn bootstrap ->
        put_in(bootstrap, ["starter_skill", "digest"], "596d1368")
      end)

      assert {:error, error} = verify(bundle)
      assert error.code == :catalog_bundle_invalid
      assert error.details["digest"] == inspect("596d1368")
    end

    @tag :tmp_dir
    test "a chosen digest beside an address nobody has chosen yet is accepted",
         %{tmp_dir: tmp_dir} do
      bundle = CatalogFixture.copy!(tmp_dir)

      assert verify(bundle) == :ok

      bootstrap = bundle |> CatalogFixture.read!("bootstrap.json") |> Jason.decode!()

      assert bootstrap["starter_skill"]["object_url"] == "https://placeholder.invalid/unchosen"

      assert bootstrap["starter_skill"]["digest"] ==
               "sha256:596d1368ac157975accce7ceff835eed6bfb789eaf68528a0aefa25a68793b0b"

      assert bootstrap["placeholder_release"] == true
    end
  end

  defp verify(bundle) do
    case Verifier.verify_bundle(Bundle.load!(bundle)) do
      :ok -> :ok
      {:error, %Error{} = error} -> {:error, error}
    end
  end
end
