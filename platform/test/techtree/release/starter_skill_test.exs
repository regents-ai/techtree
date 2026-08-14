defmodule Techtree.Release.StarterSkillTest do
  @moduledoc """
  The starter Skill is one file, and its address is the digest of that file.

  The digest is written into the module rather than computed from disk, so these
  tests are what proves the two agree: the bytes this release ships are the
  bytes the pinned digest names, and a release whose file drifted from it
  publishes nothing at all.
  """

  use ExUnit.Case, async: false

  alias Techtree.Catalog.Digest
  alias Techtree.Release.StarterSkill
  alias Techtree.ReleaseFixture

  # The file digest of
  # `techtree-python/release/skills/hello-world-starter-v1/SKILL.md`, which is
  # the source of truth for these bytes.
  @file_digest "sha256:2aff27070177d9f37b99d5bef6fa372586887e78180005195cb808971ae55a4c"

  test "the shipped file is the one the release pinned" do
    assert StarterSkill.digest() == @file_digest
    assert Digest.hash_bytes(ReleaseFixture.starter_skill_bytes()) == @file_digest
  end

  test "the bytes come back exactly, as markdown" do
    assert {:ok, bytes, media_type} = StarterSkill.bytes()

    assert bytes == ReleaseFixture.starter_skill_bytes()
    assert media_type == "text/markdown"
  end

  test "only the file digest addresses it" do
    assert StarterSkill.addressed_by?(@file_digest)

    # The digest of the one-file Skill tree the CLI builds after fetching. It
    # names the mounted bundle, never the URL that serves the file.
    refute StarterSkill.addressed_by?(
             "sha256:596d1368ac157975accce7ceff835eed6bfb789eaf68528a0aefa25a68793b0b"
           )
  end

  describe "when the file on disk drifted" do
    @describetag :tmp_dir

    test "it is refused rather than published", %{tmp_dir: tmp_dir} do
      release = ReleaseFixture.copy!(tmp_dir)
      ReleaseFixture.use_release(release)
      ReleaseFixture.write_starter_skill!(release, "# not the approved Skill\n")

      assert {:error, error} = StarterSkill.bytes()
      assert error.code == :catalog_object_digest_mismatch
      assert error.details["expected_digest"] == @file_digest
    end

    test "a release that ships no starter Skill reports it missing", %{tmp_dir: tmp_dir} do
      release = ReleaseFixture.copy!(tmp_dir)
      ReleaseFixture.use_release(release)
      File.rm!(Path.join(release, StarterSkill.relative_path()))

      assert {:error, error} = StarterSkill.bytes()
      assert error.code == :catalog_object_missing
      refute error.details["path"] =~ tmp_dir
    end
  end
end
