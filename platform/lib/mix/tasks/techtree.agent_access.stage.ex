defmodule Mix.Tasks.Techtree.AgentAccess.Stage do
  @shortdoc "Stage the pinned agent access package for the release image"

  @moduledoc """
  Copy `regent_agent_access` from the pinned `elixir-utils` snapshot into
  `vendor/regent_agent_access`, which the Dockerfile builds from.

      $ REGENT_AGENT_ACCESS_REVISION=FULL_REVISION mix techtree.agent_access.stage

  The snapshot must be at that revision, and the copied files must match its
  `.regent-files.json`. Nothing is deployed.
  """

  use Mix.Task

  @entries ~w(lib mix.exs .formatter.exs)
  @marker ".regent-agent-access-generated"

  @impl Mix.Task
  def run([]) do
    source = Map.fetch!(Mix.Project.deps_paths(), :regent_agent_access)
    snapshot = Path.dirname(source)
    revision = System.get_env("REGENT_AGENT_ACCESS_REVISION")

    unless is_binary(revision) and revision =~ ~r/\A[0-9a-f]{40}\z/ and
             File.read(Path.join(snapshot, ".regent-revision")) == {:ok, revision <> "\n"},
           do:
             Mix.raise(
               "Stage requires a pinned elixir-utils snapshot and REGENT_AGENT_ACCESS_REVISION"
             )

    expected =
      snapshot
      |> Path.join(".regent-files.json")
      |> File.read!()
      |> Jason.decode!()
      |> Enum.flat_map(fn
        {"agent_access/" <> relative, value} -> [{relative, value}]
        _other -> []
      end)
      |> Map.new()

    destination = Path.expand("vendor/regent_agent_access")
    staging = Path.expand("vendor/.regent-agent-access-stage")

    if File.exists?(destination) and not File.regular?(Path.join(destination, @marker)),
      do: Mix.raise("Refusing to replace an unrecognized #{destination}")

    File.rm_rf!(staging)
    File.mkdir_p!(staging)

    for entry <- @entries,
        do: File.cp_r!(Path.join(source, entry), Path.join(staging, entry))

    unless map_size(expected) > 0 and digests(staging) == expected,
      do: Mix.raise("regent_agent_access differs from its pinned snapshot")

    File.write!(Path.join(staging, @marker), revision <> "\n")
    File.rm_rf!(destination)
    File.rename!(staging, destination)
    Mix.shell().info("Staged regent_agent_access at #{revision}; no deployment performed")
  end

  defp digests(root) do
    root
    |> Path.join("**")
    |> Path.wildcard(match_dot: true)
    |> Enum.reject(&(File.lstat!(&1).type == :directory))
    |> Map.new(fn path ->
      unless File.lstat!(path).type == :regular,
        do: Mix.raise("regent_agent_access must contain regular files only")

      digest = :crypto.hash(:sha256, File.read!(path)) |> Base.encode16(case: :lower)
      {Path.relative_to(path, root), %{"kind" => "file", "sha256" => digest}}
    end)
  end
end
