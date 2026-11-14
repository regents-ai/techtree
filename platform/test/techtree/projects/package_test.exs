defmodule Techtree.Projects.PackageTest do
  # Reading a package the team uploads (`Techtree.Projects.Package`):
  # - a package made the way the factory makes it, one folder holding it all,
  #   reads, with its manifest, report, checksum and size, for each verdict,
  #   and with or without the tar's folder entries;
  # - each kind of bad package is refused, for its own reason: the archive
  #   itself (not gzip, cut short, more after it, over 5 MB, over 25 MB
  #   unpacked, over 2,000 entries, empty, a link, a path from the root or
  #   through `..`, a file twice), its folder (a file or a second folder beside
  #   it, no folder at all, a name with other than lower-case letters, digits
  #   and hyphens), the files against the manifest (unlisted, missing, the
  #   wrong size or sha256), the manifest (another format or line, a key twice,
  #   a key too many or missing, hidden characters, solved more than attempted,
  #   files out of order) and the report (not UTF-8).
  use ExUnit.Case, async: true

  import Techtree.ProjectPackage, only: [at: 1]

  alias Techtree.ProjectPackage
  alias Techtree.Projects.Package

  test "a package made the way the factory makes it reads whole" do
    bytes = ProjectPackage.build()

    assert {:ok, package} = Package.read(bytes)
    assert package.manifest["title"] == "Refund routing"
    assert package.report == ProjectPackage.files()["report.md"]
    assert package.size == byte_size(bytes)
    assert package.sha256 == :sha256 |> :crypto.hash(bytes) |> Base.encode16(case: :lower)

    assert Enum.map(package.manifest["files"], & &1["path"]) ==
             Enum.sort(Map.keys(ProjectPackage.files()))
  end

  test "each verdict reads, and a certainty not measured is allowed" do
    for verdict <- ~w(improved inconclusive not_improved) do
      bytes =
        ProjectPackage.build(
          manifest: fn manifest ->
            manifest |> Map.put("verdict", verdict) |> put_in(["summary", "p_value"], nil)
          end
        )

      assert {:ok, %{manifest: %{"verdict" => ^verdict}}} = Package.read(bytes)
    end
  end

  test "a tar without its folder entries reads" do
    bytes = ProjectPackage.build(entries: &Enum.reject(&1, fn {_path, c} -> c == :directory end))

    assert {:ok, %{manifest: %{"title" => "Refund routing"}}} = Package.read(bytes)
  end

  test "everything must sit in one folder, named in lower-case letters, digits and hyphens" do
    flat = fn entries ->
      for {path, contents} <- entries,
          path != ProjectPackage.folder() <> "/",
          do: {String.replace_prefix(path, ProjectPackage.folder() <> "/", ""), contents}
    end

    for {opts, reason} <- [
          {[entries: &(&1 ++ [{"notes.md", "x"}])], "notes.md outside a folder"},
          {[entries: &(&1 ++ [{"other/", :directory}])], "other"},
          {[entries: &(&1 ++ [{"other/notes.md", "x"}])], "other"},
          {[entries: flat], "manifest.json outside a folder"},
          {[entries: &Enum.map(&1, fn {path, c} -> {"./" <> path, c} end)], "folder is ."},
          {[folder: "Refund-routing"], "Refund-routing"},
          {[folder: "refund_routing"], "refund_routing"},
          {[folder: "refund routing"], "refund routing"}
        ] do
      assert {:error, message} = Package.read(ProjectPackage.build(opts))
      assert message =~ reason
    end

    assert {:error, "The package is empty."} = Package.read(ProjectPackage.tar_gz([]))
  end

  test "an archive that isn't a whole gzipped tar is refused" do
    valid = ProjectPackage.build()

    for bytes <- [
          "not a package",
          binary_part(valid, 0, byte_size(valid) - 12),
          valid <> :zlib.gzip("more"),
          valid <> "more",
          :zlib.gzip(:crypto.strong_rand_bytes(4_000))
        ] do
      assert {:error, _message} = Package.read(bytes)
    end
  end

  test "a package over 5 MB, or over 25 MB unpacked, is refused" do
    assert {:error, _message} = Package.read(:crypto.strong_rand_bytes(Package.max_bytes() + 1))

    files = Map.put(ProjectPackage.files(), "original/large.bin", :binary.copy(<<0>>, 26_214_401))
    bytes = ProjectPackage.build(files: files)

    assert byte_size(bytes) < Package.max_bytes()
    assert {:error, message} = Package.read(bytes)
    assert message =~ "25 MB"
  end

  test "a package of more than 2,000 entries is refused" do
    files =
      Map.new(1..1_987, &{"cases/final/case-#{&1}.json", "{}"})
      |> Map.merge(ProjectPackage.files())

    # The folder and the five inside it, the manifest, seven files and 1,987
    # cases: 2,001 entries.
    assert {:error, message} = Package.read(ProjectPackage.build(files: files))
    assert message =~ "2,000"

    # One fewer reads.
    files = Map.delete(files, "cases/final/case-1987.json")
    assert {:ok, _package} = Package.read(ProjectPackage.build(files: files))
  end

  test "a link, a path from the root or through .., and a file twice are refused" do
    for {entry, reason} <- [
          {{at("original/link.md"), {:symlink, "SKILL.md"}}, "a link"},
          {{"/" <> at("original/escape.md"), "x"}, "/" <> at("original/escape.md")},
          {{at("original/../../escape.md"), "x"}, at("original/../../escape.md")},
          {{at("rerun/run.sh"), "again"}, "twice"}
        ] do
      bytes = ProjectPackage.build(entries: &(&1 ++ [entry]))

      assert {:error, message} = Package.read(bytes)
      assert message =~ reason
    end
  end

  test "the files must be exactly those listed, each its size and sha256" do
    cases = [
      {[entries: &(&1 ++ [{at("original/extra.md"), "x"}])], "original/extra.md"},
      {[entries: &List.keydelete(&1, at("rerun/run.sh"), 0)], "rerun/run.sh"},
      {[manifest: &listed(&1, "selected/SKILL.md", "size_bytes", 1)], "selected/SKILL.md"},
      {[manifest: &listed(&1, "selected/SKILL.md", "sha256", String.duplicate("0", 64))],
       "selected/SKILL.md"}
    ]

    for {opts, place} <- cases do
      assert {:error, message} = Package.read(ProjectPackage.build(opts))
      assert message =~ place
    end
  end

  test "a manifest that strays from its format is refused" do
    cases = [
      {&Map.put(&1, "schema", "uplift-package/2"), "schema"},
      {&Map.put(&1, "line", "models"), "line"},
      {&Map.put(&1, "verdict", "better"), "verdict"},
      {&Map.put(&1, "price", "100"), "price"},
      {&Map.delete(&1, "success"), "success"},
      {&Map.put(&1, "title", "Refund\u202Erouting"), "title"},
      {&Map.put(&1, "job_id", String.upcase(&1["job_id"])), "job_id"},
      {&Map.put(&1, "created_at", "2026-11-14T09:30:00+01:00"), "created_at"},
      {&put_in(&1, ["summary", "original", "solved"], 7), "summary.original"},
      {&put_in(&1, ["summary", "selected", "candidate"], "other"), "summary.selected.candidate"},
      {&put_in(&1, ["summary", "pass_bar"], 1.5), "summary.pass_bar"},
      {&put_in(&1, ["summary", "cost_cents"], 1250), "summary.cost_cents"},
      {&put_in(&1, ["selection", Access.at(1), "solved"], 9), "selection[1]"},
      {&put_in(&1, ["cases", Access.at(0), "selected_solved"], 4), "cases[0]"},
      {&put_in(&1, ["setup", "limits", "nested"], %{"no" => 1}), "setup.limits.nested"},
      {&Map.update!(&1, "files", fn files -> Enum.reverse(files) end), "files"}
    ]

    for {change, place} <- cases do
      assert {:error, message} = Package.read(ProjectPackage.build(manifest: change))
      assert message =~ place
    end
  end

  test "a manifest naming a key twice is refused" do
    bytes =
      ProjectPackage.build(
        entries: fn entries ->
          {path, "{" <> rest} = List.keyfind(entries, at("manifest.json"), 0)
          List.keyreplace(entries, path, 0, {path, ~s({"title":"Another title",) <> rest})
        end
      )

    assert {:error, message} = Package.read(bytes)
    assert message =~ "title"
  end

  test "a report that isn't UTF-8 text is refused" do
    files = Map.put(ProjectPackage.files(), "report.md", <<0xFF, 0xFE, 0xFD>>)

    assert {:error, message} = Package.read(ProjectPackage.build(files: files))
    assert message =~ "report.md"
  end

  defp listed(manifest, path, key, value) do
    Map.update!(manifest, "files", fn files ->
      Enum.map(files, &if(&1["path"] == path, do: Map.put(&1, key, value), else: &1))
    end)
  end
end
