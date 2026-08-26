defmodule Techtree.Catalog.VerifierTest do
  use ExUnit.Case, async: true

  alias Techtree.Catalog.Bundle
  alias Techtree.Catalog.Error
  alias Techtree.Catalog.Verifier
  alias Techtree.CatalogFixture
  alias Techtree.Release.StarterSkill

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
        put_in(
          bootstrap,
          ["cli", "install_argv"],
          "uv tool install --python 3.12 techtree==0.1.0"
        )
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
      for field <- ["file_digest", "tree_digest"] do
        bundle = CatalogFixture.copy!(Path.join(tmp_dir, field))

        CatalogFixture.rewrite_bootstrap!(bundle, fn bootstrap ->
          put_in(bootstrap, ["starter_skill", field], "596d1368")
        end)

        assert {:error, error} = verify(bundle), "#{field} was accepted"
        assert error.code == :catalog_bundle_invalid
        assert error.details["digest"] == inspect("596d1368")
      end
    end

    @tag :tmp_dir
    test "a starter Skill that does not say how many bytes it is, is rejected",
         %{tmp_dir: tmp_dir} do
      bundle = CatalogFixture.copy!(tmp_dir)

      CatalogFixture.rewrite_bootstrap!(bundle, fn bootstrap ->
        put_in(bootstrap, ["starter_skill", "size"], 0)
      end)

      assert {:error, error} = verify(bundle)
      assert error.details["field"] == "starter_skill.size"
    end

    @tag :tmp_dir
    test "both chosen digests beside an address nobody has chosen yet are accepted",
         %{tmp_dir: tmp_dir} do
      bundle = CatalogFixture.copy!(tmp_dir)

      assert verify(bundle) == :ok

      bootstrap = bundle |> CatalogFixture.read!("bootstrap.json") |> Jason.decode!()

      assert bootstrap["starter_skill"]["object_url"] == "https://placeholder.invalid/unchosen"
      assert bootstrap["starter_skill"]["file_digest"] == StarterSkill.file_digest()
      assert bootstrap["starter_skill"]["tree_digest"] == StarterSkill.tree_digest()
      assert bootstrap["placeholder_release"] == true
    end
  end

  describe "a release that states it is not a placeholder" do
    @tag :tmp_dir
    test "is accepted when every coordinate is concrete", %{tmp_dir: tmp_dir} do
      bundle = CatalogFixture.copy!(tmp_dir)

      CatalogFixture.rewrite_bootstrap!(bundle, &CatalogFixture.concrete_release/1)

      assert verify(bundle) == :ok
    end

    @tag :tmp_dir
    test "cannot be made by flipping the flag on the placeholder release", %{tmp_dir: tmp_dir} do
      bundle = CatalogFixture.copy!(tmp_dir)

      CatalogFixture.rewrite_bootstrap!(bundle, &Map.put(&1, "placeholder_release", false))

      assert {:error, error} = verify(bundle)
      assert error.code == :catalog_bundle_invalid
      assert error.details["field"] == "cli.version"
      assert error.message =~ "states it is not a placeholder"
    end

    @tag :tmp_dir
    test "is refused for every placeholder-shaped value", %{tmp_dir: tmp_dir} do
      rejections = [
        {["cli", "version"], "0.0.0-placeholder", "cli.version"},
        {["cli", "version"], "latest", "cli.version"},
        {["cli", "version"], "0.0.0", "cli.version"},
        {["cli", "version"], "", "cli.version"},
        {["cli", "distribution"], "", "cli.distribution"},
        {["cli", "source_revision"], "a1b2c3d", "cli.source_revision"},
        {["cli", "source_revision"], String.duplicate("0", 40), "cli.source_revision"},
        {["hermes_plugin", "revision"], "main", "hermes_plugin.revision"},
        {["hermes_plugin", "revision"], String.upcase(String.duplicate("a", 40)),
         "hermes_plugin.revision"},
        {["hermes_plugin", "repository"], "techtree-hermes", "hermes_plugin.repository"},
        {["minimums", "hermes_version"], "latest", "minimums.hermes_version"},
        {["starter_skill", "object_url"], "https://placeholder.invalid/unchosen",
         "starter_skill.object_url"},
        {["starter_skill", "file_digest"], "sha256:" <> String.duplicate("0", 64),
         "starter_skill.file_digest"},
        {["starter_skill", "tree_digest"], "sha256:" <> String.duplicate("0", 64),
         "starter_skill.tree_digest"}
      ]

      for {path, value, field} <- rejections do
        bundle = spoiled_bundle(tmp_dir, field <> inspect(value), &put_in(&1, path, value))

        assert {:error, error} = verify(bundle), "#{field} = #{inspect(value)} was accepted"
        assert error.code == :catalog_bundle_invalid
        assert error.details["field"] == field
      end
    end

    @tag :tmp_dir
    test "is refused when an install instruction names a moving target", %{tmp_dir: tmp_dir} do
      bundle =
        spoiled_bundle(tmp_dir, "argv", fn bootstrap ->
          put_in(bootstrap, ["hermes_plugin", "install_argv"], [
            "hermes",
            "plugins",
            "install",
            "regents-ai/techtree-hermes",
            "--ref",
            "main",
            "--enable"
          ])
        end)

      assert {:error, error} = verify(bundle)
      assert error.details["field"] == "hermes_plugin.install_argv.5"
    end

    @tag :tmp_dir
    test "is refused when an image is named by tag rather than by digest", %{tmp_dir: tmp_dir} do
      bundle =
        spoiled_bundle(tmp_dir, "image", fn bootstrap ->
          Map.put(bootstrap, "runtime", %{"image" => "ghcr.io/regents-ai/techtree:0.1.0"})
        end)

      assert {:error, error} = verify(bundle)
      assert error.details["field"] == "runtime.image"
      assert error.message =~ "by digest"
    end

    @tag :tmp_dir
    test "is refused when something fetchable has no hash beside it", %{tmp_dir: tmp_dir} do
      bundle =
        spoiled_bundle(tmp_dir, "unhashed", fn bootstrap ->
          Map.put(bootstrap, "engine", %{
            "object_url" => "https://techtree.test/api/v1/objects/engine"
          })
        end)

      assert {:error, error} = verify(bundle)
      assert error.details["field"] == "engine.object_url"
      assert error.message =~ "no hash beside it"
    end

    @tag :tmp_dir
    test "is refused when the starter Skill address is keyed by the tree digest",
         %{tmp_dir: tmp_dir} do
      bundle =
        spoiled_bundle(tmp_dir, "tree-keyed", fn bootstrap ->
          put_in(
            bootstrap,
            ["starter_skill", "object_url"],
            "https://techtree.test/api/v1/objects/" <> StarterSkill.tree_digest()
          )
        end)

      assert {:error, error} = verify(bundle)
      assert error.details["field"] == "starter_skill.object_url"
      assert error.message =~ "digest of the file it returns"
    end

    @tag :tmp_dir
    test "keeps accepting the placeholder release it is not", %{tmp_dir: tmp_dir} do
      bundle = CatalogFixture.copy!(tmp_dir)

      assert verify(bundle) == :ok

      bootstrap = bundle |> CatalogFixture.read!("bootstrap.json") |> Jason.decode!()

      assert bootstrap["placeholder_release"] == true
      assert bootstrap["cli"]["version"] == "0.0.0-placeholder"
      assert bootstrap["starter_skill"]["object_url"] == "https://placeholder.invalid/unchosen"
    end
  end

  defp spoiled_bundle(tmp_dir, label, spoil) do
    bundle = CatalogFixture.copy!(Path.join(tmp_dir, Base.url_encode64(label, padding: false)))

    CatalogFixture.rewrite_bootstrap!(bundle, fn bootstrap ->
      bootstrap |> CatalogFixture.concrete_release() |> spoil.()
    end)

    bundle
  end

  defp verify(bundle) do
    case Verifier.verify_bundle(Bundle.load!(bundle)) do
      :ok -> :ok
      {:error, %Error{} = error} -> {:error, error}
    end
  end
end
