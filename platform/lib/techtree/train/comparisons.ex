defmodule Techtree.Train.Comparisons do
  @moduledoc """
  The comparisons the Train pages show: an NVIDIA Nemotron model measured
  before and after one change, a Skill or RL training, on the same held-out
  tasks with the same settings.

  Each comparison is two files in the configured folder
  (`config :techtree, #{inspect(__MODULE__)}, folder: ...`, as
  `{:priv, subdirectory}` for the copy shipped in the release or as a plain
  path), named by the comparison's slug:

    * `<slug>.json` — the report, `techtree.train.v1alpha1`, kind `Comparison`
    * `<slug>.traces.jsonl` — every task's exchange with the model, as the
      runner wrote it

  A report names itself by `digest`: `sha256:` and the hex SHA-256 of the
  canonical JSON (`Techtree.Canonical`) of its `schema_version`, `kind` and
  `spec`. It names its traces by `traces_digest`, the SHA-256 of the traces
  file's exact bytes. Both are worked out again on every read, and a report
  whose digest or traces do not match is refused: it is left out and logged,
  never shown.

  Every field the pages draw is matched exactly: a missing or different field
  raises rather than drawing something else. The first arm is the model with
  no change, the second the same model with the change; every task carries
  one reward and one solved mark for each, in that order. Nothing the pages
  draw is taken on the report's word where its tasks can show it: each arm's
  solved count and the paired wins, ties and losses are counted again from
  the tasks and must agree. The mean rewards, the mean difference and its
  interval are drawn as the report gives them.
  """

  require Logger

  alias Techtree.Canonical
  alias Techtree.Catalog.Digest

  @schema_version "techtree.train.v1alpha1"
  @kind "Comparison"

  @slug ~r/\A[a-z0-9]+(?:-[a-z0-9]+)*\z/
  @cost ~r/\A\d+\.\d+\z/

  @outcomes %{
    "uplift" => :uplift,
    "tie" => :tie,
    "regression" => :regression,
    "inconclusive" => :inconclusive
  }

  @type change :: :skill | :rl
  @type outcome :: :uplift | :tie | :regression | :inconclusive
  @type result :: :win | :tie | :loss
  @type refusal :: :digest | :traces

  @type arm :: %{
          name: String.t(),
          change: :none | change(),
          skill_digest: String.t() | nil,
          adapter: String.t() | nil,
          mean_reward: number(),
          solved: non_neg_integer(),
          tokens: %{prompt: non_neg_integer(), completion: non_neg_integer()}
        }

  @type task :: %{
          id: String.t(),
          rewards: {number(), number()},
          solved: {boolean(), boolean()},
          result: result()
        }

  @type t :: %{
          slug: String.t(),
          digest: String.t(),
          traces_digest: String.t(),
          title: String.t(),
          change: change(),
          environment: %{
            id: String.t(),
            version: String.t(),
            split: String.t(),
            seed: integer(),
            task_count: pos_integer(),
            taskset_digest: String.t()
          },
          model: %{
            family: String.t(),
            name: String.t(),
            provider: String.t(),
            weights_digest: String.t()
          },
          sampling: %{temperature: number(), max_tokens: pos_integer(), thinking: boolean()},
          software: %{verifiers: String.t(), techtree_lab: String.t()},
          arms: [arm()],
          tasks: [task()],
          paired: %{
            wins: non_neg_integer(),
            ties: non_neg_integer(),
            losses: non_neg_integer(),
            mean_difference: number(),
            ci95: {number(), number()},
            method: String.t()
          },
          outcome: outcome(),
          operational: %{
            started_at: DateTime.t(),
            finished_at: DateTime.t(),
            host: String.t(),
            cost_usd: String.t(),
            duration_seconds: number()
          }
        }

  @doc "The configured folder of reports."
  @spec folder() :: Path.t()
  def folder do
    case Application.fetch_env!(:techtree, __MODULE__) |> Keyword.fetch!(:folder) do
      {:priv, subdirectory} -> Application.app_dir(:techtree, ["priv", subdirectory])
      path when is_binary(path) -> path
    end
  end

  @doc """
  Every comparison in `folder` that checks out, newest first (by when its
  run finished, then by slug). A refused one is logged and left out.
  """
  @spec list(Path.t()) :: [t()]
  def list(folder \\ folder()) do
    folder
    |> read_all()
    |> Enum.flat_map(&shown/1)
    |> Enum.sort_by(&{-DateTime.to_unix(&1.operational.finished_at, :microsecond), &1.slug})
  end

  @doc """
  One comparison by its slug, or `:error` when the folder has none by that
  name or it was refused. The slug is looked up among the folder's own
  reports, never used as a path.
  """
  @spec fetch(String.t(), Path.t()) :: {:ok, t()} | :error
  def fetch(slug, folder \\ folder()) do
    with {:ok, slug} <- listed(folder, slug),
         [comparison] <- shown({slug, read(folder, slug)}) do
      {:ok, comparison}
    else
      _missing_or_refused -> :error
    end
  end

  @doc """
  The exact bytes of one comparison's report or traces file with the digest
  of those bytes, only for a comparison that checks out.
  """
  @spec download(String.t(), :report | :traces, Path.t()) :: {:ok, binary(), String.t()} | :error
  def download(slug, file, folder \\ folder()) do
    with {:ok, slug} <- listed(folder, slug),
         {report, traces} = files(folder, slug),
         [_comparison] <- shown({slug, verify(slug, report, traces)}) do
      bytes = if file == :report, do: report, else: traces
      {:ok, bytes, Digest.hash_bytes(bytes)}
    else
      _missing_or_refused -> :error
    end
  end

  @doc """
  Every report in `folder` by slug, in slug order, each read and checked:
  `{:ok, comparison}` or `{:error, :digest | :traces}`.
  """
  @spec read_all(Path.t()) :: [{String.t(), {:ok, t()} | {:error, refusal()}}]
  def read_all(folder), do: Enum.map(slugs(folder), &{&1, read(folder, &1)})

  # -- Reading ---------------------------------------------------------------

  defp shown({_slug, {:ok, comparison}}), do: [comparison]

  defp shown({slug, {:error, refusal}}) do
    Logger.warning("Train comparison #{slug} refused: #{refusal} mismatch")
    []
  end

  defp listed(folder, slug) do
    if slug in slugs(folder), do: {:ok, slug}, else: :error
  end

  # The folder's reports, by the name of each `.json` file in it. A folder
  # that is not there yet has none.
  defp slugs(folder) do
    folder
    |> Path.join("*.json")
    |> Path.wildcard()
    |> Enum.map(&Path.basename(&1, ".json"))
    |> Enum.map(fn slug ->
      true = Regex.match?(@slug, slug)
      slug
    end)
    |> Enum.sort()
  end

  # The slug is one of the folder's own file names (`slugs/1`).
  # sobelow_skip ["Traversal.FileModule"]
  defp files(folder, slug) do
    {File.read!(Path.join(folder, slug <> ".json")),
     File.read!(Path.join(folder, slug <> ".traces.jsonl"))}
  end

  defp read(folder, slug) do
    {report, traces} = files(folder, slug)
    verify(slug, report, traces)
  end

  defp verify(slug, report, traces) do
    %{
      "schema_version" => @schema_version,
      "kind" => @kind,
      "spec" => %{"traces_digest" => traces_digest} = spec,
      "operational" => operational,
      "digest" => digest
    } = Jason.decode!(report)

    named = %{"schema_version" => @schema_version, "kind" => @kind, "spec" => spec}

    cond do
      canonical_digest(named) != digest -> {:error, :digest}
      Digest.hash_bytes(traces) != traces_digest -> {:error, :traces}
      true -> {:ok, comparison(slug, digest, spec, operational)}
    end
  end

  defp canonical_digest(value), do: value |> Canonical.encode!() |> Digest.hash_bytes()

  defp comparison(slug, digest, spec, operational) do
    %{
      "title" => title,
      "environment" => %{
        "id" => environment,
        "version" => version,
        "split" => "held_out" = split,
        "seed" => seed,
        "task_count" => task_count,
        "taskset_digest" => taskset_digest
      },
      "model" => %{
        "family" => family,
        "name" => model,
        "provider" => provider,
        "weights_digest" => weights_digest
      },
      "sampling" => %{
        "temperature" => temperature,
        "max_tokens" => max_tokens,
        "thinking" => thinking
      },
      "arms" => [before_arm, after_arm],
      "software" => %{"verifiers" => verifiers, "techtree_lab" => techtree_lab},
      "results" => %{
        "arms" => [before_result, after_result],
        "per_task" => per_task,
        "paired" => paired,
        "outcome" => outcome
      },
      "traces_digest" => traces_digest
    } = spec

    true =
      Enum.all?(
        [title, environment, version, family, model, provider, verifiers, techtree_lab],
        &(is_binary(&1) and &1 != "")
      )

    true = Enum.all?([taskset_digest, weights_digest, traces_digest], &Digest.valid?/1)
    true = is_integer(seed) and is_integer(task_count) and task_count > 0
    true = is_number(temperature) and is_integer(max_tokens) and max_tokens > 0
    true = is_boolean(thinking)

    tasks = tasks(per_task, task_count)
    before = arm(unchanged(before_arm), before_result, tasks, 0)
    changed = arm(changed(after_arm), after_result, tasks, 1)
    false = before.name == changed.name

    %{
      slug: slug,
      digest: digest,
      traces_digest: traces_digest,
      title: title,
      change: changed.change,
      environment: %{
        id: environment,
        version: version,
        split: split,
        seed: seed,
        task_count: task_count,
        taskset_digest: taskset_digest
      },
      model: %{family: family, name: model, provider: provider, weights_digest: weights_digest},
      sampling: %{temperature: temperature, max_tokens: max_tokens, thinking: thinking},
      software: %{verifiers: verifiers, techtree_lab: techtree_lab},
      arms: [before, changed],
      tasks: tasks,
      paired: paired(paired, tasks),
      outcome: Map.fetch!(@outcomes, outcome),
      operational: operational(operational)
    }
  end

  # The first arm is the model as it is: no change and no Skill.
  defp unchanged(%{"name" => name, "change" => "none", "skill_digest" => nil}),
    do: %{name: name, change: :none, skill_digest: nil, adapter: nil}

  # The second is the same model with one change: a Skill, named by its
  # digest, or RL training, named by its adapter.
  defp changed(%{"name" => name, "change" => "skill", "skill_digest" => skill_digest}) do
    true = Digest.valid?(skill_digest)
    %{name: name, change: :skill, skill_digest: skill_digest, adapter: nil}
  end

  defp changed(%{"name" => name, "change" => "rl", "skill_digest" => nil, "adapter" => adapter})
       when is_binary(adapter) and adapter != "",
       do: %{name: name, change: :rl, skill_digest: nil, adapter: adapter}

  defp arm(%{name: name} = arm, result, tasks, side) do
    %{
      "name" => ^name,
      "mean_reward" => mean_reward,
      "solved" => solved,
      "tokens" => %{"prompt" => prompt, "completion" => completion}
    } = result

    true = is_binary(name) and name != "" and reward?(mean_reward)
    true = count?(prompt) and count?(completion)
    ^solved = Enum.count(tasks, &elem(&1.solved, side))

    Map.merge(arm, %{
      mean_reward: mean_reward,
      solved: solved,
      tokens: %{prompt: prompt, completion: completion}
    })
  end

  # One task per held-out task, each named once, with a reward and a solved
  # mark for each arm. The changed arm wins a task when its reward is higher.
  defp tasks(per_task, task_count) do
    tasks =
      Enum.map(per_task, fn %{
                              "task_id" => id,
                              "rewards" => [before, changed],
                              "solved" => [before_solved, changed_solved]
                            } ->
        true = is_binary(id) and id != "" and reward?(before) and reward?(changed)
        true = is_boolean(before_solved) and is_boolean(changed_solved)

        %{
          id: id,
          rewards: {before, changed},
          solved: {before_solved, changed_solved},
          result: result(before, changed)
        }
      end)

    ^task_count = length(tasks)
    ^task_count = tasks |> Enum.uniq_by(& &1.id) |> length()
    tasks
  end

  defp result(before, changed) when changed > before, do: :win
  defp result(before, changed) when changed < before, do: :loss
  defp result(_before, _changed), do: :tie

  defp paired(paired, tasks) do
    %{
      "wins" => wins,
      "ties" => ties,
      "losses" => losses,
      "mean_difference" => mean_difference,
      "ci95" => [low, high],
      "method" => method
    } = paired

    ^wins = Enum.count(tasks, &(&1.result == :win))
    ^ties = Enum.count(tasks, &(&1.result == :tie))
    ^losses = Enum.count(tasks, &(&1.result == :loss))
    true = is_number(mean_difference) and is_number(low) and is_number(high) and low <= high
    true = is_binary(method) and method != ""

    %{
      wins: wins,
      ties: ties,
      losses: losses,
      mean_difference: mean_difference,
      ci95: {low, high},
      method: method
    }
  end

  defp operational(%{
         "started_at" => started_at,
         "finished_at" => finished_at,
         "host" => host,
         "cost_usd" => cost_usd,
         "duration_seconds" => duration_seconds
       }) do
    {:ok, started_at, _offset} = DateTime.from_iso8601(started_at)
    {:ok, finished_at, _offset} = DateTime.from_iso8601(finished_at)

    true =
      is_binary(host) and host != "" and is_binary(cost_usd) and Regex.match?(@cost, cost_usd)

    true = is_number(duration_seconds) and duration_seconds >= 0

    %{
      started_at: started_at,
      finished_at: finished_at,
      host: host,
      cost_usd: cost_usd,
      duration_seconds: duration_seconds
    }
  end

  defp reward?(value), do: is_number(value) and value >= 0 and value <= 1
  defp count?(value), do: is_integer(value) and value >= 0
end
