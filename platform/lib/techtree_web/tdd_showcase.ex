defmodule TechtreeWeb.TddShowcase do
  @moduledoc """
  The one example comparison this site shows: Matt Pocock's `tdd` Skill
  against no Skill, from the files of one local `techtree forge` comparison.

  The folder is configured (`config :techtree, TechtreeWeb.TddShowcase,
  folder: ...`), as `{:priv, subdirectory}` for the copy shipped in the
  release or as a plain path. The page links the export folder in the
  repository (`repository_url`) at the full revision of the commit that added
  it (`export_revision`), since this site links no address that can move. The
  folder holds exactly what the CLI wrote:

    * `comparison.json` — the `forge compare` record of the two runs
    * `runs/baseline/spec.json`, `runs/candidate/spec.json` — each run's
      specification, as `forge run` wrote it
    * `claims-and-tasks.json` — the accepted proposal's claims and tasks
    * `export/README.md` and `export/export.json` — from `forge export` of
      the collection the runs used
    * `skill/<name>/` — the Skill's files as the run with the Skill carried
      them, its licence (`LICENSE.txt`) among them

  Only the fields the page draws are read, and each is matched exactly: a
  missing or different field raises rather than drawing something else.
  Nothing the page draws is taken on the comparison's word where the files
  can show it:

    * each run's specification has the fingerprint the comparison gives it,
      and the two differ only in the arm and the Skill
    * each Skill file has its recorded fingerprint and size, and the
      Skill's fingerprint is worked out again from them
    * the export's README is the one its record names, and the export is of
      the collection the runs used, with the same tasks in the same parts
    * each task's result, and each part's counts and verdict, are worked out
      again from the scores, by the CLI's rules, and must agree with what
      the comparison stored

  Nothing here is signed. It is one comparison on one computer, reported by
  the person who ran it, and the page says so.
  """

  alias Techtree.Canonical
  alias Techtree.Catalog.Digest

  @type verdict :: :improved | :regressed | :mixed | :no_difference | :inconclusive
  @type outcome :: :better | :worse | :same | :not_scored
  @type run :: :baseline | :candidate

  @type attempt_end ::
          :not_recorded
          | :agent_timed_out
          | :agent_failed
          | :outputs_rejected
          | :verifier_timed_out
          | :no_verdict

  @type task :: %{
          id: String.t(),
          name: String.t(),
          claim: String.t(),
          kind: String.t(),
          part: :study | :held_out,
          summary: String.t(),
          time_limit: String.t(),
          baseline_reward: float() | nil,
          candidate_reward: float() | nil,
          outcome: outcome(),
          unscored: [%{run: run(), ended: attempt_end()}]
        }

  @type part :: %{
          verdict: verdict(),
          wins: non_neg_integer(),
          losses: non_neg_integer(),
          ties: non_neg_integer(),
          unresolved: non_neg_integer(),
          graded: non_neg_integer(),
          baseline_mean: float() | nil,
          candidate_mean: float() | nil,
          tasks: [task()]
        }

  @type t :: %{
          comparison_id: String.t(),
          created_at: DateTime.t(),
          collection_id: String.t(),
          fingerprint: String.t(),
          skill: %{
            name: String.t(),
            digest: String.t(),
            files: [%{path: String.t(), text: String.t()}],
            licence: %{name: String.t(), copyright: String.t()}
          },
          model: %{provider: String.t(), model_id: String.t(), reasoning: String.t() | nil},
          limits: %{cpus: pos_integer(), memory_mb: pos_integer()},
          not_established: [:served_model | :agent_unmodified | :sampling],
          held_out: part(),
          study: part(),
          tasks: [task()],
          claims: [
            %{id: String.t(), statement: String.t(), observable: String.t(), tasks: [task()]}
          ],
          arms: %{
            baseline: %{api_calls: non_neg_integer() | nil, total_tokens: non_neg_integer() | nil},
            candidate: %{
              api_calls: non_neg_integer() | nil,
              total_tokens: non_neg_integer() | nil
            }
          },
          commands: [[String.t()]]
        }

  # Fewer graded pairs than this and no verdict is given: the CLI's
  # `VERDICT_MINIMUM_PAIRS` (cli/src/techtree/forge/models.py).
  @verdict_minimum_pairs 3

  # Where the release's copy of this folder is committed in the repository.
  @published_folder "platform/priv/examples/tdd-showcase"

  @licence "LICENSE.txt"

  @verdicts %{
    "improved" => :improved,
    "regressed" => :regressed,
    "mixed" => :mixed,
    "no_difference" => :no_difference,
    "inconclusive" => :inconclusive
  }

  @results %{better: "win", worse: "loss", same: "tie", not_scored: "unresolved"}

  @attempt_ends %{
    nil => :not_recorded,
    "agent_timed_out" => :agent_timed_out,
    "agent_failed" => :agent_failed,
    "outputs_rejected" => :outputs_rejected,
    "verifier_timed_out" => :verifier_timed_out,
    "no_verdict" => :no_verdict
  }

  # What a local comparison cannot establish, as the CLI words it
  # (`NOT_ESTABLISHED`, cli/src/techtree/forge/experiment.py).
  @not_established %{
    "which model the provider actually served: Hermes' usage report is the only witness, and it is self-reported" =>
      :served_model,
    "that the Hermes executable is unmodified: its version is what it prints" =>
      :agent_unmodified,
    "the provider's sampling settings: Hermes exposes no temperature or seed, so every attempt uses the provider's default" =>
      :sampling
  }

  @doc "The configured showcase folder."
  @spec folder() :: Path.t()
  def folder do
    case Keyword.fetch!(config(), :folder) do
      {:priv, subdirectory} -> Application.app_dir(:techtree, ["priv", subdirectory])
      path when is_binary(path) -> path
    end
  end

  @doc """
  Where a reader finds the committed export folder of these tasks: the
  configured repository at the configured revision, the commit that added
  this folder, so the address never moves under the reader.
  """
  @spec export_url() :: String.t()
  def export_url do
    config = config()
    revision = Keyword.fetch!(config, :export_revision)
    true = Regex.match?(~r/\A[0-9a-f]{40}\z/, revision)

    Keyword.fetch!(config, :repository_url) <> "/tree/#{revision}/#{@published_folder}/export"
  end

  @doc "The fewest tasks scored on both runs that a verdict needs."
  @spec verdict_minimum_pairs() :: pos_integer()
  def verdict_minimum_pairs, do: @verdict_minimum_pairs

  @doc """
  Read the showcase from `folder`, raising on any file or field that is
  missing, does not match, or disagrees with another.
  """
  @spec load!(Path.t()) :: t()
  def load!(folder) do
    %{
      "schema_version" => "techtree.forge-comparison.v1alpha5",
      "comparison_id" => comparison_id,
      "created_at" => created_at,
      "tasks_from" =>
        %{
          "kind" => "collection",
          "collection_id" => collection_id,
          "collection_digest" => fingerprint
        } = tasks_from,
      "baseline_skill" => nil,
      "source_skill" => %{"name" => skill_name, "digest" => skill_digest} = skill,
      "candidate_skill" => skill,
      "comparability" => %{
        "controlled" => true,
        "violations" => [],
        "baseline_configuration_digest" => baseline_spec_digest,
        "candidate_configuration_digest" => candidate_spec_digest,
        "differences" => [
          %{"pointer" => "/arm"},
          %{"pointer" => "/skill", "baseline" => nil, "candidate" => recorded_skill}
        ]
      },
      "baseline" => baseline,
      "candidate" => candidate,
      "pairs" => pairs,
      "repetitions" => 1,
      "study" => stored_study,
      "held_out" => stored_held_out,
      "not_established" => not_established
    } = read_json!(folder, "comparison.json")

    %{
      "arm" => "baseline",
      "skill" => nil,
      "tasks_from" => ^tasks_from,
      "task_ids" => task_ids,
      "model" => %{"provider" => provider, "model_id" => model_id, "reasoning" => reasoning},
      "limits" => %{
        "agent_budget" => "task-timeout",
        "turns" => "unbounded",
        "container_cpus" => cpus,
        "container_memory_mb" => memory_mb,
        "network" => false
      },
      "sampling" => %{"control" => "provider-default", "repetitions" => 1},
      "not_established" => ^not_established
    } = baseline_spec = spec!(folder, "baseline", baseline_spec_digest)

    %{"arm" => "candidate", "skill" => ^recorded_skill} =
      candidate_spec = spec!(folder, "candidate", candidate_spec_digest)

    true = Map.drop(baseline_spec, ["arm", "skill"]) == Map.drop(candidate_spec, ["arm", "skill"])

    %{
      "schema_version" => "techtree.forge-export.v1alpha3",
      "readme_digest" => readme_digest,
      "collection" => %{
        "collection_id" => ^collection_id,
        "collection_digest" => ^fingerprint,
        "review" => %{"members" => members}
      }
    } = read_json!(folder, "export/export.json")

    readme = File.read!(Path.join([folder, "export", "README.md"]))
    ^readme_digest = Digest.hash_bytes(readme)
    true = String.contains?(readme, fingerprint)

    %{"claims" => claims, "tasks" => proposed} = read_json!(folder, "claims-and-tasks.json")

    tasks = tasks(pairs, task_ids, members, proposed, time_limits(readme, members))
    files = skill_files!(folder, skill_name, skill_digest, recorded_skill)
    {:ok, created_at, 0} = DateTime.from_iso8601(created_at)

    %{
      comparison_id: comparison_id,
      created_at: created_at,
      collection_id: collection_id,
      fingerprint: fingerprint,
      skill: %{
        name: skill_name,
        digest: skill_digest,
        files: files,
        licence: licence(files)
      },
      model: %{provider: provider, model_id: model_id, reasoning: reasoning},
      limits: %{cpus: cpus, memory_mb: memory_mb},
      not_established: Enum.map(not_established, &Map.fetch!(@not_established, &1)),
      held_out: part!(stored_held_out, :held_out, tasks),
      study: part!(stored_study, :study, tasks),
      tasks: tasks,
      claims: claims(claims, tasks),
      arms: %{baseline: arm(baseline), candidate: arm(candidate)},
      commands: commands(readme)
    }
  end

  @doc """
  The tasks of one part, split by how the Skill changed them.
  """
  @spec by_outcome([task()]) :: %{outcome() => [task()]}
  def by_outcome(tasks) do
    Map.merge(
      %{better: [], worse: [], same: [], not_scored: []},
      Enum.group_by(tasks, & &1.outcome)
    )
  end

  # -- Reading ---------------------------------------------------------------

  defp config, do: Application.fetch_env!(:techtree, __MODULE__)

  defp read_json!(folder, relative),
    do: folder |> Path.join(relative) |> File.read!() |> Jason.decode!()

  # One run's specification, which must be the one the comparison names by
  # its fingerprint: the digest of its canonical JSON, as the CLI's
  # `run_spec_digest` works it out (cli/src/techtree/forge/experiment.py).
  defp spec!(folder, arm, digest) do
    %{"schema_version" => "techtree.forge-run-spec.v1alpha2"} =
      spec = read_json!(folder, Path.join(["runs", arm, "spec.json"]))

    ^digest = canonical_digest(spec)
    spec
  end

  defp canonical_digest(value), do: value |> Canonical.encode!() |> Digest.hash_bytes()

  # One task per pair, in the runs' order: one attempt per task, so one pair
  # each, and exactly the collection's members.
  defp tasks(pairs, task_ids, members, proposed, time_limits) do
    members = Map.new(members, &{&1["task_id"], &1})
    proposed = Map.new(proposed, &{&1["name"], &1})
    ^task_ids = Enum.map(pairs, & &1["task_id"])
    true = Enum.sort(task_ids) == Enum.sort(Map.keys(members))

    Enum.map(pairs, fn pair ->
      %{
        "task_id" => id,
        "attempt" => 1,
        "baseline_outcome" => baseline_end,
        "baseline_reward" => baseline,
        "candidate_outcome" => candidate_end,
        "candidate_reward" => candidate,
        "result" => result
      } = pair

      outcome = outcome(baseline, candidate)
      ^result = Map.fetch!(@results, outcome)

      %{"task_name" => name, "claim" => claim, "kind" => kind, "part" => part} =
        Map.fetch!(members, id)

      %{"summary" => summary} = Map.fetch!(proposed, name)

      %{
        id: id,
        name: name,
        claim: claim,
        kind: kind,
        part: part(part),
        summary: summary,
        time_limit: Map.fetch!(time_limits, name),
        baseline_reward: baseline,
        candidate_reward: candidate,
        outcome: outcome,
        unscored:
          unscored(:baseline, baseline_end, baseline) ++
            unscored(:candidate, candidate_end, candidate)
      }
    end)
  end

  # A pair is scored only when both runs were graded; then the Skill made the
  # task better, worse or no different (`_pair`, cli/src/techtree/forge/compare.py).
  defp outcome(baseline, candidate) when is_nil(baseline) or is_nil(candidate), do: :not_scored
  defp outcome(baseline, candidate) when candidate > baseline, do: :better
  defp outcome(baseline, candidate) when candidate < baseline, do: :worse
  defp outcome(_baseline, _candidate), do: :same

  # A run that has a score was graded; one that has none says how its attempt
  # ended, or left none at all.
  defp unscored(_run, "graded", reward) when is_number(reward), do: []

  defp unscored(run, ended, nil) when ended != "graded",
    do: [%{run: run, ended: Map.fetch!(@attempt_ends, ended)}]

  defp part("study"), do: :study
  defp part("held_out"), do: :held_out

  # One part added up and judged again from its tasks' scores by the CLI's
  # rules (`_part`, cli/src/techtree/forge/compare.py), which must agree with
  # what the comparison stored for it.
  defp part!(stored, part, tasks) do
    own = Enum.filter(tasks, &(&1.part == part))
    ids = Enum.map(own, & &1.id)
    graded = Enum.reject(own, &(&1.outcome == :not_scored))
    wins = Enum.count(graded, &(&1.outcome == :better))
    losses = Enum.count(graded, &(&1.outcome == :worse))
    ties = Enum.count(graded, &(&1.outcome == :same))
    graded_count = length(graded)
    unresolved = length(own) - graded_count
    verdict = verdict(wins, losses, graded_count, unresolved)

    %{
      "task_ids" => ^ids,
      "pairs_planned" => planned,
      "pairs_graded" => ^graded_count,
      "wins" => ^wins,
      "losses" => ^losses,
      "ties" => ^ties,
      "unresolved" => ^unresolved,
      "verdict" => stored_verdict
    } = stored

    ^planned = length(own)
    ^verdict = Map.fetch!(@verdicts, stored_verdict)

    %{
      verdict: verdict,
      wins: wins,
      losses: losses,
      ties: ties,
      unresolved: unresolved,
      graded: graded_count,
      baseline_mean: mean(graded, & &1.baseline_reward),
      candidate_mean: mean(graded, & &1.candidate_reward),
      tasks: own
    }
  end

  # The verdict rules, in their order (`forge_verdict`,
  # cli/src/techtree/forge/models.py).
  defp verdict(_wins, _losses, graded, unresolved)
       when unresolved > 0 or graded < @verdict_minimum_pairs,
       do: :inconclusive

  defp verdict(wins, losses, _graded, _unresolved) when wins > 0 and losses > 0, do: :mixed
  defp verdict(wins, _losses, _graded, _unresolved) when wins > 0, do: :improved
  defp verdict(_wins, losses, _graded, _unresolved) when losses > 0, do: :regressed
  defp verdict(_wins, _losses, _graded, _unresolved), do: :no_difference

  defp mean([], _reward), do: nil
  defp mean(tasks, reward), do: tasks |> Enum.map(reward) |> Enum.sum() |> Kernel./(length(tasks))

  # The claims the accepted tasks test, in the proposal's order, each with
  # its tasks; a claim no accepted task tests is left out, as the export's
  # README leaves it out.
  defp claims(claims, tasks) do
    claims
    |> Enum.map(fn %{"claim_id" => id, "statement" => statement, "observable" => observable} ->
      %{
        id: id,
        statement: statement,
        observable: observable,
        tasks: Enum.filter(tasks, &(&1.claim == id))
      }
    end)
    |> Enum.reject(&(&1.tasks == []))
  end

  defp arm(%{"api_calls" => api_calls, "total_tokens" => total_tokens}),
    do: %{api_calls: api_calls, total_tokens: total_tokens}

  # The Skill's files as the run with the Skill recorded them, each read from
  # the folder and matched against its recorded fingerprint and size, and
  # nothing more. The Skill's own fingerprint is the digest of that file list,
  # as the CLI's `skill_content_digest` works it out
  # (cli/src/techtree/manifests/builder.py).
  defp skill_files!(folder, name, digest, recorded_skill) do
    %{"name" => ^name, "root_digest" => ^digest, "files" => recorded} = recorded_skill
    ^digest = canonical_digest(recorded)

    root = Path.join([folder, "skill", name])
    paths = Enum.map(recorded, & &1["path"])

    true =
      Enum.sort(paths) ==
        root
        |> Path.join("**")
        |> Path.wildcard(match_dot: true)
        |> Enum.reject(&File.dir?/1)
        |> Enum.map(&Path.relative_to(&1, root))
        |> Enum.sort()

    Enum.map(recorded, fn %{
                            "path" => path,
                            "media_type" => _type,
                            "size" => size,
                            "digest" => file_digest
                          } ->
      bytes = File.read!(Path.join(root, path))
      ^size = byte_size(bytes)
      ^file_digest = Digest.hash_bytes(bytes)
      %{path: path, text: bytes}
    end)
  end

  # The licence is one of the Skill's own files: its first line names it, and
  # it carries one copyright line.
  defp licence(files) do
    %{text: text} = Enum.find(files, &(&1.path == @licence))
    [name | lines] = String.split(text, "\n")
    [copyright] = Enum.filter(lines, &String.starts_with?(&1, "Copyright"))
    %{name: name, copyright: copyright}
  end

  # The time limit the export's README gives each task, by name.
  defp time_limits(readme, members) do
    [_before, section] = String.split(readme, "### What the model calls can cost\n", parts: 2)
    [section | _after] = String.split(section, "\n###", parts: 2)

    Map.new(members, fn %{"task_name" => name} ->
      [_line, limit] = Regex.run(~r/^- #{Regex.escape(name)}: (.+)$/m, section)
      {name, limit}
    end)
  end

  # The commands the export's README lists, in order, as argv.
  defp commands(readme) do
    [_before, block] = String.split(readme, "### The commands, in order\n\n```\n", parts: 2)
    [block | _after] = String.split(block, "\n```", parts: 2)
    [_ | _] = lines = String.split(block, "\n")
    Enum.map(lines, &String.split(&1, " "))
  end
end
