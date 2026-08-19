defmodule Techtree.Release.CandidateTest do
  @moduledoc """
  The release candidate this repository carries but does not serve.

  `priv/releases/climb-v0.1.0` holds the exact bytes Gate 2 is asked to
  approve: a bootstrap release that states `placeholder_release: false` and
  therefore promises that every coordinate in it is real. Decision 0023 forbids
  approving one document and activating another, so the bytes are built before
  approval and activated unchanged afterwards — which only means anything if
  they are checked now, by the same validation that will check them at import.

  So this suite does four things. It proves decision 0007 R10 accepts the
  candidate, through the real import path rather than by calling the rule
  directly. It proves that acceptance is not vacuous, by spoiling one
  coordinate of the candidate at a time and watching the same path refuse it.
  It proves the candidate is still not what this build publishes: the contract
  in `priv/bootstrap` remains a declared placeholder, and the pointer is not
  this suite's to move. And it proves the release channel has a floor to roll
  back to — `priv/bootstrap/stable.json`, the release that will be staged
  underneath the candidate on the channel the candidate names, which decision
  0027 requires to be believable as a release and useless as an installation.
  """

  use ExUnit.Case, async: true

  alias Techtree.Catalog.Bundle
  alias Techtree.Catalog.Digest
  alias Techtree.Catalog.Error
  alias Techtree.Catalog.Verifier
  alias Techtree.CatalogFixture
  alias Techtree.Release.StarterSkill

  @release_id "climb-v0.1.0"

  # The route this application already publishes content-addressed bytes at.
  @object_route "https://techtree.sh/api/v1/objects/"

  # What a placeholder release puts where a commit belongs.
  @unset_revision String.duplicate("0", 40)

  setup do
    %{
      bootstrap: decode("bootstrap.json"),
      core: decode("release-core.json"),
      checksums: decode("checksums.json")
    }
  end

  describe "the coordinates" do
    test "the candidate states that none of them are placeholders", %{bootstrap: bootstrap} do
      assert bootstrap["placeholder_release"] == false
      assert bootstrap["schema_version"] == "techtree.bootstrap.v1alpha1"
    end

    test "the CLI is pinned to a version, a source commit and a wheel", %{
      bootstrap: bootstrap,
      checksums: checksums
    } do
      assert bootstrap["cli"]["distribution"] == "techtree"
      assert bootstrap["cli"]["version"] == "0.1.0"
      assert bootstrap["cli"]["source_revision"] =~ ~r/\A[0-9a-f]{40}\z/
      assert bootstrap["cli"]["install_argv"] == ["uv", "tool", "install", "techtree==0.1.0"]
      assert bootstrap["cli"]["wheel_sha256"] == checksums["coordinates"]["cli_wheel"]
    end

    test "the plugin is pinned to a commit at the regents-ai coordinate", %{
      bootstrap: bootstrap,
      checksums: checksums
    } do
      plugin = bootstrap["hermes_plugin"]
      commit = checksums["sources"]["hermes_plugin_commit"]

      assert plugin["repository"] == "regents-ai/techtree-hermes"
      assert plugin["revision"] == commit
      assert commit =~ ~r/\A[0-9a-f]{40}\z/

      assert plugin["install_argv"] == [
               "hermes",
               "plugins",
               "install",
               "regents-ai/techtree-hermes",
               "--ref",
               commit,
               "--enable"
             ]
    end

    test "the host Hermes minimum is the one the release was tested against", %{
      bootstrap: bootstrap,
      core: core
    } do
      assert bootstrap["minimums"]["hermes_version"] == core["minimum_host_hermes_version"]
      assert core["minimum_host_hermes_version"] == "0.20.1"
      assert core["maximum_tested_host_hermes_version"] == "0.20.1"
    end

    test "the introductory Climb is the one the ReleaseCore names", %{
      bootstrap: bootstrap,
      core: core
    } do
      assert bootstrap["introductory_climb"]["reference"] == core["intro_climb_reference"]
    end
  end

  describe "the starter Skill" do
    test "is addressed by the digest of the file the address returns", %{bootstrap: bootstrap} do
      starter = bootstrap["starter_skill"]

      assert starter["name"] == StarterSkill.name()
      assert starter["media_type"] == StarterSkill.media_type()
      assert starter["size"] == StarterSkill.size()
      assert starter["file_digest"] == StarterSkill.file_digest()
      assert starter["object_url"] == @object_route <> StarterSkill.file_digest()
    end

    test "names the tree digest the ReleaseCore pins, and never as an address", %{
      bootstrap: bootstrap,
      core: core
    } do
      starter = bootstrap["starter_skill"]

      assert starter["tree_digest"] == core["starter_skill_digest"]
      assert starter["tree_digest"] == StarterSkill.tree_digest()
      refute starter["tree_digest"] == starter["file_digest"]
      refute String.contains?(starter["object_url"], starter["tree_digest"])
    end

    test "is the file this application serves at that address" do
      assert {:ok, bytes, media_type} = StarterSkill.bytes()
      assert Digest.hash_bytes(bytes) == StarterSkill.file_digest()
      assert byte_size(bytes) == StarterSkill.size()
      assert media_type == StarterSkill.media_type()
    end
  end

  describe "the artifacts beside it" do
    test "the ReleaseCore copy is the one every repository shares", %{
      core: core,
      checksums: checksums
    } do
      assert Digest.hash_bytes(read("release-core.json")) ==
               checksums["files"]["release-core.json"]

      assert checksums["files"]["release-core.json"] ==
               checksums["sources"]["release_core_digest"]

      assert core["schema_version"] == "techtree.release-core.v1"
    end

    test "the checksums describe the bytes that are actually there", %{checksums: checksums} do
      recorded = checksums["files"]

      present =
        directory()
        |> File.ls!()
        |> Enum.reject(&(&1 == "checksums.json"))
        |> Enum.sort()

      assert present == Enum.sort(Map.keys(recorded))

      for {name, digest} <- recorded do
        assert Digest.hash_bytes(read(name)) == digest, "#{name} is not #{digest}"
      end
    end

    test "the candidate bootstrap digest is recorded", %{checksums: checksums} do
      assert checksums["release_id"] == @release_id
      assert Digest.valid?(checksums["files"]["bootstrap.json"])
    end
  end

  describe "decision 0007 R10" do
    @tag :tmp_dir
    test "accepts the candidate through the path an import takes", %{tmp_dir: tmp_dir} do
      assert verify(bundle_with_candidate(tmp_dir, & &1)) == :ok
    end

    @tag :tmp_dir
    test "refuses the candidate with any one coordinate made placeholder-like",
         %{tmp_dir: tmp_dir} do
      spoilings = [
        {["cli", "version"], "0.0.0-placeholder", "cli.version"},
        {["cli", "version"], "latest", "cli.version"},
        {["cli", "source_revision"], String.duplicate("0", 40), "cli.source_revision"},
        {["cli", "source_revision"], "38e242b", "cli.source_revision"},
        {["cli", "wheel_sha256"], "", "cli.wheel_sha256"},
        {["hermes_plugin", "revision"], "main", "hermes_plugin.revision"},
        {["hermes_plugin", "repository"], "techtree-hermes", "hermes_plugin.repository"},
        {["minimums", "hermes_version"], "latest", "minimums.hermes_version"},
        {["starter_skill", "object_url"], "https://placeholder.invalid/unchosen",
         "starter_skill.object_url"},
        {["starter_skill", "file_digest"], "sha256:" <> String.duplicate("0", 64),
         "starter_skill.file_digest"},
        {["starter_skill", "tree_digest"], "sha256:" <> String.duplicate("0", 64),
         "starter_skill.tree_digest"}
      ]

      for {path, value, field} <- spoilings do
        bundle =
          bundle_with_candidate(
            Path.join(tmp_dir, Base.url_encode64(field <> value, padding: false)),
            &put_in(&1, path, value)
          )

        assert {:error, error} = verify(bundle), "#{field} = #{inspect(value)} was accepted"
        assert error.code == :catalog_bundle_invalid
        assert error.details["field"] == field
      end
    end

    @tag :tmp_dir
    test "refuses the candidate addressed at its own tree digest", %{tmp_dir: tmp_dir} do
      bundle =
        bundle_with_candidate(tmp_dir, fn bootstrap ->
          put_in(
            bootstrap,
            ["starter_skill", "object_url"],
            @object_route <> bootstrap["starter_skill"]["tree_digest"]
          )
        end)

      assert {:error, error} = verify(bundle)
      assert error.details["field"] == "starter_skill.object_url"
    end
  end

  describe "what this build still publishes" do
    test "the contract it ships is a declared placeholder, and not the candidate", %{
      checksums: checksums
    } do
      assert published()["placeholder_release"] == true
      assert published()["cli"]["version"] == "0.0.0-placeholder"

      assert Digest.hash_bytes(published_bytes()) != checksums["files"]["bootstrap.json"]
    end

    test "the placeholder it ships asks for the same host Hermes the candidate does", %{
      bootstrap: bootstrap
    } do
      assert published()["minimums"]["hermes_version"] ==
               bootstrap["minimums"]["hermes_version"]
    end

    test "the placeholder it ships names the starter Skill the same way", %{
      bootstrap: bootstrap
    } do
      assert Map.delete(published()["starter_skill"], "object_url") ==
               Map.delete(bootstrap["starter_skill"], "object_url")
    end
  end

  describe "the rollback floor of the candidate's channel" do
    test "is a release on the same channel that says it is a placeholder", %{
      bootstrap: bootstrap
    } do
      assert floor()["channel"] == bootstrap["channel"]
      assert floor()["placeholder_release"] == true
      assert floor()["schema_version"] == "techtree.bootstrap.v1alpha1"
    end

    test "carries no coordinate anything could be installed from" do
      floor = floor()

      assert floor["cli"]["version"] == "0.0.0-placeholder"
      assert floor["cli"]["source_revision"] == @unset_revision

      assert floor["cli"]["install_argv"] == [
               "uv",
               "tool",
               "install",
               "techtree==0.0.0-placeholder"
             ]

      refute Map.has_key?(floor["cli"], "wheel_sha256")
      assert floor["hermes_plugin"]["revision"] == @unset_revision
      assert @unset_revision in floor["hermes_plugin"]["install_argv"]
      assert floor["starter_skill"]["object_url"] == "https://placeholder.invalid/unchosen"
    end

    test "asks for the same host Hermes and names the same starter Skill bytes", %{
      bootstrap: bootstrap
    } do
      assert floor()["minimums"] == bootstrap["minimums"]

      assert Map.delete(floor()["starter_skill"], "object_url") ==
               Map.delete(bootstrap["starter_skill"], "object_url")
    end

    @tag :tmp_dir
    test "is accepted by the validation an import runs, as a placeholder", %{tmp_dir: tmp_dir} do
      assert verify(bundle_publishing(tmp_dir, floor())) == :ok
    end

    test "is a different release from the candidate", %{checksums: checksums} do
      assert Digest.hash_bytes(floor_bytes()) != checksums["files"]["bootstrap.json"]
    end
  end

  # -- Helpers ----------------------------------------------------------------

  defp directory do
    Application.app_dir(:techtree, ["priv", "releases", @release_id])
  end

  defp read(name), do: File.read!(Path.join(directory(), name))

  defp decode(name), do: name |> read() |> Jason.decode!()

  # The bootstrap release this build ships and `scripts/sync_catalog.exs` copies
  # into the bundle it serves.
  defp published_bytes do
    File.read!(Application.app_dir(:techtree, "priv/bootstrap/development.json"))
  end

  defp published, do: published_bytes() |> Jason.decode!()

  # The release the candidate's channel keeps underneath it, so that rolling
  # back is a pointer move onto staged bytes rather than onto nothing.
  defp floor_bytes do
    File.read!(Application.app_dir(:techtree, "priv/bootstrap/stable.json"))
  end

  defp floor, do: floor_bytes() |> Jason.decode!()

  # The candidate bootstrap, published by a bundle that ships the Climb it
  # names, so that the full import verification runs against it.
  defp bundle_with_candidate(destination, spoil) do
    bundle_publishing(destination, spoil.(decode("bootstrap.json")))
  end

  # A bundle that ships the fixture catalog and publishes `document` as its
  # bootstrap release, which is what an import is handed.
  defp bundle_publishing(destination, document) do
    bundle = CatalogFixture.copy!(destination)
    CatalogFixture.rewrite_bootstrap!(bundle, fn _fixture -> document end)
    bundle
  end

  defp verify(bundle) do
    case Verifier.verify_bundle(Bundle.load!(bundle)) do
      :ok -> :ok
      {:error, %Error{} = error} -> {:error, error}
    end
  end
end
