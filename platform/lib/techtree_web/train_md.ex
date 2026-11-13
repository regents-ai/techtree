defmodule TechtreeWeb.TrainMD do
  @moduledoc """
  A comparison's page as Markdown, the same figures and words as its HTML
  (`TechtreeWeb.TrainCopy`), answered at the page's own address
  (`TechtreeWeb.Plugs.PageMarkdown`).
  """

  use TechtreeWeb, :verified_routes

  alias TechtreeWeb.TrainCopy, as: Copy

  @doc "`/train/:slug`: one comparison in full."
  @spec show(Techtree.Train.Comparisons.t()) :: String.t()
  def show(comparison) do
    %{environment: environment, model: model, sampling: sampling, paired: paired} = comparison
    operational = comparison.operational

    arms =
      Enum.map_join(comparison.arms, "\n", fn arm ->
        "- #{Copy.arm_label(comparison, arm)} (`#{arm.name}`): mean reward #{Copy.percent(arm.mean_reward)}, " <>
          "#{Copy.solved(arm, environment.task_count)}, " <>
          "#{Copy.number(arm.completion_tokens)} completion tokens#{change(arm)}"
      end)

    [before, changed] = Enum.map(comparison.arms, &Copy.arm_label(comparison, &1))

    tasks =
      Enum.map_join(comparison.tasks, "\n", fn %{rewards: {before, changed}} = task ->
        "| `#{task.id}` | #{Copy.reward(before)} | #{Copy.reward(changed)} | #{Copy.result(task.result)} |"
      end)

    """
    # #{comparison.title}

    #{model.family} on #{environment.task_count} held-out tasks of #{environment.id}, with the same settings on both sides. Finished #{Copy.date(operational.finished_at)}.

    ## Result

    - #{figures(comparison)}
    - Outcome: #{Copy.outcome(comparison.outcome)}
    - Tasks: #{Copy.paired(paired)}
    - Interval: #{Copy.interval(paired.ci95)} points, the 95% range of the difference, by #{paired.method}

    #{Copy.reading(comparison)}

    ## Arms

    #{arms}

    ## Tasks

    | Task | #{before} | #{changed} | Result |
    | --- | --- | --- | --- |
    #{tasks}

    ## Settings

    - Sampling: temperature #{sampling.temperature}, at most #{sampling.max_tokens} tokens, thinking #{if sampling.thinking, do: "on", else: "off"}
    - Environment: `#{environment.id}` #{environment.version}, #{String.downcase(Copy.split(environment.split))} split, seed #{environment.seed}, #{environment.task_count} tasks
    - Model: NVIDIA #{model.family}, `#{model.name}` on #{model.provider}
    - Run: #{operational.host}, started #{Copy.time(operational.started_at)}, #{Copy.duration(operational.duration_seconds)}, run cost $#{operational.cost_usd}
    - Software: verifiers #{comparison.software.verifiers}, techtree-lab #{comparison.software.techtree_lab}

    ## Evidence

    - Report: `#{comparison.digest}`, [download](#{url(~p"/train/#{comparison.slug}/report.json")})
    - Traces: `#{comparison.traces_digest}`, [download](#{url(~p"/train/#{comparison.slug}/traces.jsonl")})
    - Tasks: `#{environment.taskset_digest}`
    - Weights: `#{model.weights_digest}`
    """
  end

  defp change(%{change: :none}), do: ""
  defp change(%{change: :skill, skill_digest: digest}), do: ", Skill `#{digest}`"
  defp change(%{change: :rl, adapter: adapter}), do: ", adapter `#{adapter}`"

  defp figures(comparison) do
    arms =
      Enum.map_join(comparison.arms, " · ", fn arm ->
        "#{Copy.arm_label(comparison, arm)} #{Copy.percent(arm.mean_reward)}"
      end)

    "#{arms} · Difference #{Copy.points(comparison.paired.mean_difference)} points"
  end
end
