defmodule Techtree.Catalog.ImporterTest do
  use Techtree.DataCase, async: false

  @moduletag :capture_log

  alias Techtree.Catalog.BootstrapRelease
  alias Techtree.Catalog.CatalogEntry
  alias Techtree.Catalog.CatalogRelease
  alias Techtree.Catalog.Digest
  alias Techtree.Catalog.Error
  alias Techtree.Catalog.Importer
  alias Techtree.Catalog.Query
  alias Techtree.CatalogFixture

  describe "importing the generated catalog" do
    setup do
      CatalogFixture.use_bundle(CatalogFixture.root())
      %{release: Importer.import!(CatalogFixture.root())}
    end

    test "activates one complete release describing the bundle", %{release: release} do
      assert release.import_status == :complete
      assert release.active
      assert release.channel == "development"
      assert release.catalog_digest == CatalogFixture.catalog_digest()
      assert release.source_revision == "fedcba9876543210fedcba9876543210fedcba98"
      assert release.imported_at

      assert {:ok, active} = Query.active_catalog_release()
      assert active.id == release.id
    end

    test "stages one active entry per shipped object" do
      entries = Ash.read!(CatalogEntry)

      assert length(entries) == 5
      assert Enum.all?(entries, & &1.active)

      assert entries |> Enum.map(& &1.kind) |> Enum.sort() == [
               :campaign,
               :climb,
               :data_policy,
               :taskset_validation,
               :validation_evidence
             ]

      for entry <- entries do
        bytes = CatalogFixture.read!(CatalogFixture.root(), entry.relative_path)
        assert Digest.hash_bytes(bytes) == entry.protocol_digest
        assert entry.byte_size == byte_size(bytes)
        assert entry.media_type == "application/json"
      end
    end

    test "describes the public Climb from the graph it points at" do
      assert [climb] = Query.list_climbs()

      assert climb.reference == CatalogFixture.climb_reference()
      assert climb.title == "Techtree Hello World"
      assert climb.status == "development"
      assert climb.summary =~ "A toy Skill-uplift Climb"

      assert %{
               "slug" => "hello-world-climb",
               "version" => 1,
               "campaign_spec_digest" => campaign_digest,
               "purpose" => "component_uplift",
               "task_count" => 36,
               "taskset_id" => "procedure-transfer-v1",
               "subject_harness" => "hermes-agent",
               "subject_harness_version" => "0.19.0",
               "evaluation_backend" => "local_techtree",
               "proof_grade" => "development_only",
               "leaderboard_enabled" => false,
               "data_policy" => data_policy,
               "mutation_contract" => mutation_contract
             } = climb.projection

      assert campaign_digest == CatalogFixture.campaign_digest()
      assert mutation_contract["kind"] == "skill_insertion"

      assert data_policy == %{
               "raw_episode_server_upload" => "prohibited",
               "raw_episode_training_use" => "prohibited",
               "candidate_skill_public_release" => "required_for_climb",
               "uplift_report_visibility" => "public"
             }
    end

    test "carries no credential into the public projection" do
      assert [climb] = Query.list_climbs()

      refute climb.projection |> Jason.encode!() |> String.contains?("credential_env")
    end

    test "stores the bootstrap payload as the exact bytes it verified" do
      assert {:ok, bootstrap} = Query.active_bootstrap_release()

      expected = CatalogFixture.read!(CatalogFixture.root(), "bootstrap.json")
      assert bootstrap.raw_payload == expected
      assert bootstrap.payload_digest == Digest.hash_bytes(expected)
      assert bootstrap.cli_version == "0.0.0-placeholder"
      assert bootstrap.plugin_revision == String.duplicate("0", 40)
      assert bootstrap.minimum_hermes_version == "0.20.1"
      assert bootstrap.schema_version == "techtree.bootstrap.v1alpha1"
      assert bootstrap.placeholder_release
    end

    test "serves every object byte for byte" do
      for entry <- Ash.read!(CatalogEntry) do
        assert {:ok, bytes, served} = Query.object_bytes(entry.protocol_digest)
        assert served.protocol_digest == entry.protocol_digest
        assert served.media_type == entry.media_type
        assert bytes == CatalogFixture.read!(CatalogFixture.root(), entry.relative_path)
      end

      assert {:ok, index, digest} = Query.catalog_bytes()
      assert index == CatalogFixture.read!(CatalogFixture.root(), "catalog.json")
      assert digest == CatalogFixture.catalog_digest()
    end

    test "reimporting the same bundle is idempotent" do
      before = Ash.read!(CatalogEntry) |> Enum.map(& &1.id) |> Enum.sort()

      reimported = Importer.import!(CatalogFixture.root())

      assert Ash.read!(CatalogEntry) |> Enum.map(& &1.id) |> Enum.sort() == before
      assert Enum.count(Ash.read!(CatalogRelease), & &1.active) == 1
      assert Enum.count(Ash.read!(BootstrapRelease), & &1.active) == 1
      assert {:ok, active} = Query.active_catalog_release()
      assert active.id == reimported.id
    end
  end

  describe "importing a second bundle" do
    @describetag :tmp_dir

    setup %{tmp_dir: tmp_dir} do
      CatalogFixture.use_bundle(CatalogFixture.root())
      first = Importer.import!(CatalogFixture.root())

      %{first: first, bundle: CatalogFixture.copy!(tmp_dir)}
    end

    test "retires the object the new bundle replaced, and keeps it resolvable",
         %{bundle: bundle} do
      retired = CatalogFixture.climb_digest()
      replacement = replace_climb!(bundle)

      CatalogFixture.use_bundle(bundle)
      Importer.import!(bundle)

      assert [climb] = Query.list_climbs()
      assert climb.protocol_digest == replacement
      assert climb.reference == CatalogFixture.climb_reference()

      assert {:ok, previous} = Query.get_entry_by_digest(retired)
      refute previous.active

      assert {:ok, bytes, %{protocol_digest: ^retired}} = Query.object_bytes(retired)
      assert bytes == CatalogFixture.read!(CatalogFixture.root(), CatalogFixture.climb_path())
    end

    test "a bundle for another channel is refused", %{bundle: bundle, first: first} do
      CatalogFixture.rewrite_bootstrap!(bundle, &Map.put(&1, "channel", "stable"))

      error = assert_raise Error, fn -> Importer.import!(bundle) end
      assert error.code == :catalog_bundle_invalid

      assert {:ok, active} = Query.active_catalog_release()
      assert active.id == first.id
    end
  end

  describe "a bundle that fails while it is being staged" do
    @describetag :tmp_dir

    setup %{tmp_dir: tmp_dir} do
      CatalogFixture.use_bundle(CatalogFixture.root())
      first = Importer.import!(CatalogFixture.root())

      %{first: first, bundle: CatalogFixture.copy!(tmp_dir)}
    end

    test "leaves the previously active release untouched", %{first: first, bundle: bundle} do
      duplicate_reference!(bundle)

      assert_raise Ash.Error.Invalid, fn -> Importer.import!(bundle) end

      assert {:ok, active} = Query.active_catalog_release()
      assert active.id == first.id
      assert active.catalog_digest == CatalogFixture.catalog_digest()

      assert length(Ash.read!(CatalogEntry)) == 5
      assert Enum.all?(Ash.read!(CatalogEntry), & &1.active)
      assert Enum.count(Ash.read!(CatalogRelease), & &1.active) == 1

      assert {:ok, bootstrap} = Query.active_bootstrap_release()
      assert bootstrap.payload_digest == first.bootstrap_digest
    end

    test "records why the failed release was rolled back", %{first: first, bundle: bundle} do
      duplicate_reference!(bundle)

      assert_raise Ash.Error.Invalid, fn -> Importer.import!(bundle) end

      assert [failed] =
               CatalogRelease
               |> Ash.read!()
               |> Enum.reject(&(&1.id == first.id))

      assert failed.import_status == :failed
      refute failed.active
      assert failed.error_summary =~ "Ash.Error.Invalid"
    end

    test "a partial bundle never reaches the database", %{first: first, bundle: bundle} do
      File.rm!(Path.join(bundle, "campaigns/hello-world-climb.json"))

      error = assert_raise Error, fn -> Importer.import!(bundle) end
      assert error.code == :catalog_object_missing

      assert Ash.read!(CatalogRelease) |> Enum.map(& &1.id) == [first.id]
      assert {:ok, active} = Query.active_catalog_release()
      assert active.id == first.id
    end
  end

  # An index that files the same public reference twice passes byte and path
  # verification and is caught by the uniqueness the resource declares — which
  # is exactly the failure the staging transaction has to survive.
  defp duplicate_reference!(bundle) do
    original = CatalogFixture.read!(bundle, CatalogFixture.climb_path())
    duplicate = String.replace(original, "\"version\":1", "\"version\":1 ")
    CatalogFixture.write!(bundle, "climbs/duplicate.json", duplicate)

    CatalogFixture.rewrite_index!(bundle, fn index ->
      Map.update!(index, "climbs", fn climbs ->
        climbs ++
          [
            %{
              "reference" => CatalogFixture.climb_reference(),
              "digest" => Digest.hash_bytes(duplicate),
              "path" => "climbs/duplicate.json"
            }
          ]
      end)
    end)
  end

  # A later release of the same public Climb: new bytes at a new path, the same
  # reference, and the same Campaign underneath it.
  defp replace_climb!(bundle) do
    replacement =
      bundle
      |> CatalogFixture.read!(CatalogFixture.climb_path())
      |> String.replace(
        "Techtree Hello World",
        "Techtree Hello World, revised"
      )

    path = "climbs/hello-world-climb-revised.json"
    CatalogFixture.write!(bundle, path, replacement)
    digest = Digest.hash_bytes(replacement)

    CatalogFixture.rewrite_index!(bundle, fn index ->
      Map.update!(index, "climbs", fn [climb | rest] ->
        [%{climb | "digest" => digest, "path" => path} | rest]
      end)
    end)

    digest
  end
end
