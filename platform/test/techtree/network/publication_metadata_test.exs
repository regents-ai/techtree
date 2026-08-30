defmodule Techtree.Network.PublicationMetadataTest do
  use Techtree.DataCase, async: false

  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture
  alias Techtree.Network
  alias Techtree.Network.Ingest
  alias Techtree.Network.Projection
  alias Techtree.NetworkFixture

  @skill_digest "sha256:596d1368ac157975accce7ceff835eed6bfb789eaf68528a0aefa25a68793b0b"

  setup do
    CatalogFixture.use_bundle(CatalogFixture.root())
    Importer.import!(CatalogFixture.root())
    :ok
  end

  test "derives the campaign and candidate Skill digests from verified sources" do
    assert {:ok, entry, :recorded} = NetworkFixture.publish()

    assert entry.campaign_name == "Techtree Hello World"
    assert entry.skill_digest == @skill_digest
    assert is_nil(entry.skill_name)
    assert is_nil(entry.skill_github_url)
  end

  test "accepts the strictly shaped public Skill metadata" do
    assert {:ok, entry, :recorded} =
             NetworkFixture.publish(
               NetworkFixture.submission(),
               skill_name: "my-skill_v1",
               skill_github_url: "https://github.com/example/my-skill"
             )

    assert entry.skill_name == "my-skill_v1"
    assert entry.skill_github_url == "https://github.com/example/my-skill"
  end

  test "rejects malformed public Skill metadata before creating an entry" do
    assert {:error, %{code: :publication_skill_name_invalid}} =
             NetworkFixture.publish(NetworkFixture.submission(), skill_name: "../not-a-label")

    assert {:error, %{code: :publication_skill_github_url_invalid}} =
             NetworkFixture.publish(
               NetworkFixture.submission(),
               skill_github_url: "http://github.com/example/my-skill"
             )

    assert Network.list_publication_entries!() == []
  end

  test "a retry returns first-publication metadata and receipt unchanged" do
    assert {:ok, first, :recorded} =
             NetworkFixture.publish(
               NetworkFixture.submission(),
               skill_name: "first-label",
               skill_github_url: "https://github.com/example/first"
             )

    assert {:ok, retry, :existing} =
             NetworkFixture.publish(
               NetworkFixture.submission(),
               skill_name: "second-label",
               skill_github_url: "https://github.com/example/second"
             )

    assert retry.id == first.id
    assert retry.receipt_bytes == first.receipt_bytes
    assert retry.skill_name == "first-label"
    assert retry.skill_github_url == "https://github.com/example/first"
  end

  test "the read projection exposes metadata without exposing submission bytes" do
    assert {:ok, entry, :recorded} =
             NetworkFixture.publish(
               NetworkFixture.submission(),
               skill_name: "public-skill",
               skill_github_url: "https://github.com/example/public-skill"
             )

    projection =
      entry
      |> Projection.entry(TechtreeWeb.Endpoint.url())
      |> Jason.decode!()

    assert projection["campaign_name"] == "Techtree Hello World"
    assert projection["skill_digest"] == @skill_digest
    assert projection["skill_name"] == "public-skill"
    assert projection["skill_github_url"] == "https://github.com/example/public-skill"
    refute Map.has_key?(projection, "submission_bytes")
  end

  test "controller headers remain outside the four-member submission" do
    {:ok, key} = Techtree.Network.Key.load()

    assert {:ok, entry, :recorded} =
             Ingest.accept(
               NetworkFixture.submission(),
               key,
               skill_name: "header-label",
               skill_github_url: "https://github.com/example/header-label",
               origin: TechtreeWeb.Endpoint.url()
             )

    assert entry.submission_bytes == NetworkFixture.submission()

    assert Enum.sort(NetworkFixture.submission() |> Jason.decode!() |> Map.keys()) ==
             ~w(bundle_digest files run_id schema_version)
  end
end
