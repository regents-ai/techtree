defmodule Techtree.TrainFixture do
  @moduledoc """
  Train reports made for the tests, in the exact shape the runner writes
  (`Techtree.Train.Comparisons`), with their digests worked out the same way.

  `test/support/fixtures/train` holds two of them, the reports the pages and
  the browser walk read in the test environment, written with `write!/3`:

      write!(folder, "nemotron-nano-skill")
      write!(folder, "nemotron-lightning-rl",
        change: :rl, finished_at: "2026-11-11T08:15:00Z", results: {18, 38, 8})
  """

  alias Techtree.Canonical
  alias Techtree.Catalog.Digest

  @tasks 64
  @duration 2530

  @doc """
  The bytes of one report and its traces.

  Options: `:change` (`:skill` or `:rl`, default `:skill`), `:finished_at`
  (an ISO 8601 time in UTC; the run started 2530 seconds before), `:title`,
  `:results` (`{wins, ties, losses}`, adding up to 64) and `:outcome`.
  """
  @spec files(keyword()) :: {binary(), binary()}
  def files(opts \\ []) do
    change = Keyword.get(opts, :change, :skill)
    {wins, ties, losses} = Keyword.get(opts, :results, {30, 28, 6})
    @tasks = wins + ties + losses

    {before_name, after_name} = names(change)
    tasks = tasks(wins, ties, losses)
    traces = traces(tasks, before_name, after_name)

    spec = %{
      "title" => Keyword.get(opts, :title, title(change)),
      "environment" => %{
        "id" => "regents/payment-terms",
        "version" => "0.1.0",
        "split" => "held_out",
        "seed" => 0,
        "task_count" => @tasks,
        "taskset_digest" => Digest.hash_bytes("payment-terms held-out tasks")
      },
      "model" => model(change),
      "sampling" => %{"temperature" => 0.0, "max_tokens" => 512, "thinking" => false},
      "arms" => [
        %{"name" => before_name, "change" => "none", "skill_digest" => nil},
        changed_arm(change, after_name)
      ],
      "software" => %{"verifiers" => "0.4.1", "techtree_lab" => "0.1.0"},
      "results" => %{
        "arms" => [result(before_name, tasks, 0), result(after_name, tasks, 1)],
        "per_task" => tasks,
        "paired" => paired(tasks, wins, ties, losses),
        "outcome" => Keyword.get(opts, :outcome, "uplift")
      },
      "traces_digest" => Digest.hash_bytes(traces)
    }

    named = %{"schema_version" => "techtree.train.v1alpha1", "kind" => "Comparison", "spec" => spec}

    {:ok, finished_at, 0} =
      opts |> Keyword.get(:finished_at, "2026-11-10T09:42:10Z") |> DateTime.from_iso8601()

    report =
      Map.merge(named, %{
        "operational" => %{
          "started_at" => finished_at |> DateTime.add(-@duration) |> DateTime.to_iso8601(),
          "finished_at" => DateTime.to_iso8601(finished_at),
          "host" => if(change == :rl, do: "prime-hosted-training", else: "local"),
          "cost_usd" => if(change == :rl, do: "14.20", else: "0.00"),
          "duration_seconds" => @duration
        },
        "digest" => named |> Canonical.encode!() |> Digest.hash_bytes()
      })

    {Jason.encode_to_iodata!(report, pretty: true) |> IO.iodata_to_binary(), traces}
  end

  @doc "Write one report and its traces into `folder` under `slug`."
  @spec write!(Path.t(), String.t(), keyword()) :: :ok
  def write!(folder, slug, opts \\ []) do
    {report, traces} = files(opts)
    File.mkdir_p!(folder)
    File.write!(Path.join(folder, slug <> ".json"), report)
    File.write!(Path.join(folder, slug <> ".traces.jsonl"), traces)
  end

  defp names(:skill), do: {"baseline", "skill"}
  defp names(:rl), do: {"baseline", "trained"}

  defp title(:skill), do: "Skill on Nemotron 3 Nano 4B"
  defp title(:rl), do: "RL on Nemotron 3.5 Lightning"

  defp model(:skill),
    do: %{
      "family" => "Nemotron 3 Nano",
      "name" => "nemotron-3-nano:4b",
      "provider" => "ollama",
      "weights_digest" => Digest.hash_bytes("nemotron-3-nano:4b weights")
    }

  defp model(:rl),
    do: %{
      "family" => "Nemotron 3.5 Lightning",
      "name" => "nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16",
      "provider" => "prime-intellect",
      "weights_digest" => Digest.hash_bytes("nemotron-3.5-lightning weights")
    }

  defp changed_arm(:skill, name),
    do: %{
      "name" => name,
      "change" => "skill",
      "skill_digest" => Digest.hash_bytes("payment-terms skill")
    }

  defp changed_arm(:rl, name),
    do: %{
      "name" => name,
      "change" => "rl",
      "skill_digest" => nil,
      "adapter" => "techtree/payment-terms-lora-step-50"
    }

  # Wins, then ties (half solved by both, half by neither), then losses,
  # spread through the task order so the outcomes are mixed.
  defp tasks(wins, ties, losses) do
    pairs =
      List.duplicate({0.25, 1.0}, wins) ++
        List.duplicate({1.0, 1.0}, div(ties, 2)) ++
        List.duplicate({0.5, 0.5}, ties - div(ties, 2)) ++
        List.duplicate({1.0, 0.5}, losses)

    pairs
    |> Enum.with_index()
    |> Enum.sort_by(fn {_pair, index} -> rem(index * 37, @tasks) end)
    |> Enum.with_index()
    |> Enum.map(fn {{{before, changed}, _index}, number} ->
      %{
        "task_id" => "payment-terms-#{String.pad_leading(Integer.to_string(number), 3, "0")}",
        "rewards" => [before, changed],
        "solved" => [before == 1.0, changed == 1.0]
      }
    end)
  end

  defp result(name, tasks, side) do
    rewards = Enum.map(tasks, &Enum.at(&1["rewards"], side))

    %{
      "name" => name,
      "mean_reward" => Enum.sum(rewards) / length(rewards),
      "solved" => Enum.count(tasks, &Enum.at(&1["solved"], side)),
      "tokens" => %{"prompt" => 41_216 + side * 52_480, "completion" => 9_830 + side * 1_204}
    }
  end

  defp paired(tasks, wins, ties, losses) do
    difference =
      Enum.sum(Enum.map(tasks, fn %{"rewards" => [before, changed]} -> changed - before end)) /
        length(tasks)

    %{
      "wins" => wins,
      "ties" => ties,
      "losses" => losses,
      "mean_difference" => difference,
      "ci95" => [Float.round(difference - 0.0875, 4), Float.round(difference + 0.0875, 4)],
      "method" => "paired bootstrap, 10000 resamples, seed 0"
    }
  end

  defp traces(tasks, before_name, after_name) do
    tasks
    |> Enum.flat_map(fn %{"task_id" => id, "rewards" => [before, changed]} ->
      [
        %{"task_id" => id, "arm" => before_name, "completion" => "{}", "reward" => before},
        %{"task_id" => id, "arm" => after_name, "completion" => "{}", "reward" => changed}
      ]
    end)
    |> Enum.map_join(&(Jason.encode!(&1) <> "\n"))
  end
end
