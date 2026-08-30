defmodule Techtree.Catalog.PublicationTest do
  @moduledoc """
  Rollback, as this application performs it: a pointer moves, and nothing else.

  Two releases are imported in turn, which leaves the second one published and
  the first one still staged. Everything below is about what happens when the
  pointer is sent back to the first — the bytes the site serves change, the rows
  do not, and going forward again is the same command with the other digest.
  """

  use Techtree.DataCase, async: false

  alias Techtree.Catalog.BootstrapRelease
  alias Techtree.Catalog.Digest
  alias Techtree.Catalog.Importer
  alias Techtree.Catalog.Publication
  alias Techtree.Catalog.Query
  alias Techtree.CatalogFixture

  @unknown_digest "sha256:" <> String.duplicate("c", 64)

  setup %{tmp_dir: tmp_dir} do
    bundle = CatalogFixture.copy!(tmp_dir)
    CatalogFixture.use_bundle(bundle)

    Importer.import!(bundle)
    first = published_digest()

    CatalogFixture.rewrite_bootstrap!(
      bundle,
      &Map.put(&1, "published_at", "2026-08-14T00:00:00Z")
    )

    Importer.import!(bundle)
    second = published_digest()

    %{bundle: bundle, first: first, second: second}
  end

  @moduletag :tmp_dir

  test "an import leaves the newest release published", %{first: first, second: second} do
    refute first == second
    assert published_digest() == second
  end

  test "the pointer goes back to the previous release", %{first: first, second: second} do
    assert {:ok, switch} = Publication.publish(first)

    assert switch.published == first
    assert switch.previous == second
    assert published_digest() == first
  end

  test "the bytes the site serves are the ones the pointer selects", %{first: first} do
    assert {:ok, _switch} = Publication.publish(first)
    assert {:ok, payload, digest} = Query.bootstrap_payload()

    assert digest == first
    assert Digest.hash_bytes(payload) == first
  end

  test "going back and forward again is the same command", %{first: first, second: second} do
    assert {:ok, _back} = Publication.publish(first)
    assert {:ok, forward} = Publication.publish(second)

    assert forward.previous == first
    assert published_digest() == second
  end

  test "rolling back deletes nothing", %{first: first, second: second} do
    staged = Enum.map(Publication.list(), & &1.payload_digest)

    assert {:ok, _switch} = Publication.publish(first)

    assert Enum.sort(Enum.map(Publication.list(), & &1.payload_digest)) == Enum.sort(staged)
    assert first in staged
    assert second in staged
  end

  test "publishing the release already published changes nothing", %{second: second} do
    assert {:ok, switch} = Publication.publish(second)

    assert switch.published == second
    assert switch.previous == nil
    assert published_digest() == second
    assert Enum.count(Publication.list(), & &1.active) == 1
  end

  test "a digest this channel never staged publishes nothing", %{second: second} do
    assert {:error, error} = Publication.publish(@unknown_digest)

    assert error.code == :bootstrap_release_missing
    assert published_digest() == second
  end

  test "a value that is not a digest publishes nothing", %{second: second} do
    assert {:error, error} = Publication.publish("../../etc/passwd")

    assert error.code == :catalog_bundle_invalid
    assert published_digest() == second
  end

  test "another channel's release is not publishable here", %{second: second} do
    assert {:error, error} = Publication.publish(second, channel: "stable")

    assert error.code == :bootstrap_release_missing
    assert error.details["channel"] == "stable"
    assert published_digest() == second
  end

  test "a payload that drifted from its digest is never published", %{
    first: first,
    second: second
  } do
    release = Enum.find(Publication.list(), &(&1.payload_digest == first))

    Ash.Changeset.for_update(release, :deactivate, %{}, authorize?: false)
    |> Ash.Changeset.force_change_attribute(:raw_payload, "{}")
    |> Ash.update!(authorize?: false)

    assert {:error, error} = Publication.publish(first)

    assert error.code == :catalog_object_digest_mismatch
    assert published_digest() == second
  end

  test "the list names every staged release once, marking the published one" do
    releases = Publication.list()

    assert length(releases) == 2
    assert Enum.count(releases, & &1.active) == 1

    assert Enum.map(releases, & &1.payload_digest) ==
             Enum.uniq(Enum.map(releases, & &1.payload_digest))
  end

  test "no interface but this one may move the pointer" do
    release = Enum.find(Publication.list(), & &1.active)

    assert_raise Ash.Error.Forbidden, fn ->
      release
      |> Ash.Changeset.for_update(:deactivate, %{})
      |> Ash.update!()
    end
  end

  defp published_digest do
    assert {:ok, %BootstrapRelease{payload_digest: digest}} = Query.active_bootstrap_release()
    digest
  end
end
