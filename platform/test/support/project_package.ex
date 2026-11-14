defmodule Techtree.ProjectPackage do
  @moduledoc """
  Packages for Projects tests, made the way the factory makes them: a gzipped
  tar of `manifest.json` and the files it lists (`Techtree.Projects.Package`).
  Each part can be changed to make a package that should be refused: the
  files, the manifest, or the tar's entries themselves.
  """

  @files %{
    "report.md" => """
    # Refund routing

    The selected Skill sent **5 of 6** final attempts to the right team.

    | Case | Before | After |
    | --- | --- | --- |
    | refund-1 | 1 of 3 | 3 of 3 |
    | refund-2 | 2 of 3 | 2 of 3 |

    <script>alert("raw HTML is not shown")</script>
    """,
    "original/SKILL.md" => "# Refunds\n\nSend each refund request to billing.\n",
    "selected/SKILL.md" =>
      "# Refunds\n\nSend each refund request to the team that owns its order.\n",
    "cases/final/refund-1.json" => ~s({"ticket": "Refund for order 1001", "team": "orders"}\n),
    "cases/final/refund-2.json" => ~s({"ticket": "Refund for a gift card", "team": "billing"}\n),
    "rerun/README.md" => "Run `sh run.sh` to run the final test again.\n",
    "rerun/run.sh" => "#!/bin/sh\nset -eu\necho \"final test\"\n"
  }

  @doc "The files of a valid package, by path, without its manifest."
  @spec files() :: %{String.t() => binary()}
  def files, do: @files

  @doc "A valid manifest for `files`: the Skill improved on the final test."
  @spec manifest(%{String.t() => binary()}) :: map()
  def manifest(files \\ @files) do
    %{
      "schema" => "uplift-package/1",
      "line" => "skills",
      "title" => "Refund routing",
      "job_id" => Ecto.UUID.generate(),
      "created_at" => "2026-11-14T09:30:00Z",
      "success" => "Each refund request reaches the team that owns it.",
      "verdict" => "improved",
      "summary" => %{
        "repeats" => 3,
        "final_cases" => 2,
        "original" => %{"solved" => 3, "attempts" => 6},
        "selected" => %{"candidate" => "skillopt", "solved" => 5, "attempts" => 6},
        "difference" => 2,
        "p_value" => 0.03,
        "pass_bar" => 0.7,
        "pass_bar_met" => true,
        "regressions" => 0,
        "cost_cents" => "1250.5",
        "attempts" => 30,
        "retries" => 1
      },
      "selection" => [
        candidate("original", 3, false, false),
        candidate("rewrite", 4, false, false),
        candidate("skillopt", 5, false, true)
      ],
      "cases" => [
        %{"id" => "refund-1", "original_solved" => 1, "selected_solved" => 3, "repeats" => 3},
        %{"id" => "refund-2", "original_solved" => 2, "selected_solved" => 2, "repeats" => 3}
      ],
      "setup" => %{
        "model" => "Qwen3-32B",
        "tools" => [
          %{"name" => "SkillEvaluator", "maker" => "NVIDIA", "version" => "1.4.0"},
          %{"name" => "verifiers", "maker" => "Prime Intellect", "version" => "0.1.9"}
        ],
        "limits" => %{"max_turns" => 30, "time_per_attempt" => "10 minutes"},
        "split" => %{
          "working" => 20,
          "selection" => 10,
          "final" => 2,
          "digest" => sha256("split")
        }
      },
      "files" => listing(files)
    }
  end

  @doc "The manifest's `files`: each file's path, sha256 and size, in path order."
  @spec listing(%{String.t() => binary()}) :: [map()]
  def listing(files) do
    files
    |> Enum.sort()
    |> Enum.map(fn {path, bytes} ->
      %{"path" => path, "sha256" => sha256(bytes), "size_bytes" => byte_size(bytes)}
    end)
  end

  @doc """
  A package, as bytes. Options, each applied to the valid package's part:
  `:files` the files, `:manifest` a function given the manifest for them, and
  `:entries` a function given the tar's `{path, contents}` entries, manifest
  first. Contents are bytes, `:directory` for a folder, or `{:symlink, target}`
  for a link.
  """
  @spec build(keyword()) :: binary()
  def build(opts \\ []) do
    files = Keyword.get(opts, :files, @files)
    manifest = Keyword.get(opts, :manifest, & &1).(manifest(files))
    entries = [{"manifest.json", Jason.encode!(manifest)} | Enum.sort(files)]

    opts
    |> Keyword.get(:entries, & &1)
    |> then(& &1.(entries))
    |> tar_gz()
  end

  @doc "A gzipped tar of `entries`, as `build/1` takes them."
  @spec tar_gz([{String.t(), binary() | :directory | {:symlink, String.t()}}]) :: binary()
  def tar_gz(entries) do
    dir = Path.join(System.tmp_dir!(), "project-package-#{System.unique_integer([:positive])}")
    File.mkdir_p!(dir)
    tar = Path.join(dir, "package.tar")

    try do
      {:ok, handle} = :erl_tar.open(String.to_charlist(tar), [:write])
      Enum.each(entries, &(:ok = add(handle, dir, &1)))
      :ok = :erl_tar.close(handle)
      :zlib.gzip(File.read!(tar))
    after
      File.rm_rf!(dir)
    end
  end

  defp add(handle, dir, {path, :directory}) do
    folder = Path.join(dir, "folder-#{System.unique_integer([:positive])}")
    File.mkdir!(folder)
    :erl_tar.add(handle, String.to_charlist(folder), String.to_charlist(path), [])
  end

  defp add(handle, dir, {path, {:symlink, target}}) do
    link = Path.join(dir, "link-#{System.unique_integer([:positive])}")
    File.ln_s!(target, link)
    :erl_tar.add(handle, String.to_charlist(link), String.to_charlist(path), [])
  end

  defp add(handle, _dir, {path, bytes}) when is_binary(bytes),
    do: :erl_tar.add(handle, bytes, String.to_charlist(path), [])

  defp candidate(name, solved, refused, selected) do
    %{
      "candidate" => name,
      "solved" => solved,
      "attempts" => 6,
      "refused" => refused,
      "selected" => selected
    }
  end

  defp sha256(bytes), do: :sha256 |> :crypto.hash(bytes) |> Base.encode16(case: :lower)
end
