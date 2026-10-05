defmodule Techtree.Release.StarterSkillTest do
  @moduledoc """
  Each Climb's starter Skill is one file, and its address is the digest of that
  file.

  The digests are written into the module rather than computed from disk, so
  these tests are what proves the two agree: the bytes this release ships are
  the bytes the pinned digests name, and a release whose file drifted from its
  digest publishes nothing at all.
  """

  use ExUnit.Case, async: false

  alias Techtree.Catalog.Digest
  alias Techtree.Release.StarterSkill
  alias Techtree.ReleaseFixture

  test "every shipped file is the one the release pinned" do
    for starter <- StarterSkill.all() do
      bytes = ReleaseFixture.starter_skill_bytes(starter)

      assert Digest.hash_bytes(bytes) == starter.file_digest, starter.name
      assert byte_size(bytes) == starter.size, starter.name
    end
  end

  test "the bytes come back exactly, as markdown" do
    for starter <- StarterSkill.all() do
      assert {:ok, bytes, "text/markdown"} = StarterSkill.bytes(starter)
      assert bytes == ReleaseFixture.starter_skill_bytes(starter)
    end
  end

  test "each Climb has its own starter Skill" do
    for starter <- StarterSkill.all() do
      assert StarterSkill.for_climb(starter.climb_reference) == {:ok, starter}
    end

    assert StarterSkill.all() |> Enum.map(& &1.climb_reference) |> Enum.uniq() |> length() ==
             length(StarterSkill.all())
  end

  test "only the file digest addresses it" do
    for starter <- StarterSkill.all() do
      assert StarterSkill.addressed_by(starter.file_digest) == {:ok, starter}

      # The digest of the one-file Skill tree the CLI builds after fetching. It
      # names the mounted bundle, never the URL that serves the file.
      assert StarterSkill.addressed_by(starter.tree_digest) == :error
    end
  end

  describe "when the file on disk drifted" do
    @describetag :tmp_dir

    setup do
      {:ok, starter} = StarterSkill.for_climb("hello-world-climb@3")
      %{starter: starter}
    end

    test "it is refused rather than published", %{tmp_dir: tmp_dir, starter: starter} do
      release = ReleaseFixture.copy!(tmp_dir)
      ReleaseFixture.use_release(release)
      ReleaseFixture.write_starter_skill!(release, starter, "# not the approved Skill\n")

      assert {:error, error} = StarterSkill.bytes(starter)
      assert error.code == :catalog_object_digest_mismatch
      assert error.details["expected_digest"] == starter.file_digest
    end

    test "a release that ships no starter Skill reports it missing", %{
      tmp_dir: tmp_dir,
      starter: starter
    } do
      release = ReleaseFixture.copy!(tmp_dir)
      ReleaseFixture.use_release(release)
      File.rm!(Path.join(release, StarterSkill.relative_path(starter)))

      assert {:error, error} = StarterSkill.bytes(starter)
      assert error.code == :catalog_object_missing
      refute error.details["path"] =~ tmp_dir
    end
  end
end
