defmodule TechtreeWeb.ResultAssessment do
  @moduledoc """
  What one published Result says about keeping its Skill change, read only
  from what the Result carries.

  The verdict is the signed report's own decision, which applied the rule the
  Campaign declared before either run, together with the sign of the mean
  change. Nothing here re-decides it: a page that ran its own rule would be
  asserting a verdict nobody declared in advance.

  Tasks are named by their place in the Campaign's committed order and their
  fingerprint, because that is all a published Result holds about a task. It
  keeps neither the task's words nor the agent's answers.

  The Skill change is the difference the signed report found between the two
  runs' settings, read from the stored bytes this site accepted.
  """

  alias Techtree.Network.Bundle
  alias Techtree.Network.PublicationEntry

  @skill_pointer "/agents/subject/harness/skills/"

  @type outcome :: :better | :worse | :same

  @type task :: %{
          hash: String.t(),
          label: String.t(),
          short_hash: String.t(),
          baseline: String.t(),
          candidate: String.t(),
          delta: String.t(),
          outcome: outcome()
        }

  @type verdict :: %{outcome: :improved | :regressed | :not_enough_evidence, reason: String.t()}

  @type value ::
          :no_skill | :not_set | {:artifact, String.t(), non_neg_integer()} | {:text, String.t()}

  @doc """
  Improved, regressed, or not enough evidence, with the reason in words.
  """
  @spec verdict(PublicationEntry.t()) :: verdict()
  def verdict(%{decision: "accepted"}) do
    %{
      outcome: :improved,
      reason:
        "With the Skill, the agent scored higher, and the result clears the rule " <>
          "this Climb set before either run."
    }
  end

  def verdict(%{decision: "rejected", absolute_delta: delta}) when delta < 0 do
    %{
      outcome: :regressed,
      reason:
        "With the Skill, the agent scored lower overall, so the rule this Climb set " <>
          "before either run turns it down."
    }
  end

  def verdict(%{decision: "rejected"}) do
    %{
      outcome: :not_enough_evidence,
      reason:
        "With the Skill, the agent did not score higher by enough to clear the rule " <>
          "this Climb set before either run."
    }
  end

  def verdict(%{decision: "inconclusive"}) do
    %{
      outcome: :not_enough_evidence,
      reason: "This Climb set no rule before the runs that can decide between them."
    }
  end

  def verdict(%{decision: "invalid"}) do
    %{
      outcome: :not_enough_evidence,
      reason:
        "The two runs differed in more than the Skill, so the difference cannot be put " <>
          "down to it."
    }
  end

  def verdict(%{decision: "development_only"}) do
    %{
      outcome: :not_enough_evidence,
      reason:
        "The run's own report makes no call, because it was not signed in a way that " <>
          "lets it decide."
    }
  end

  @doc """
  Every task in the Campaign's committed order, with both scores and the change.
  """
  @spec tasks([map()]) :: [task()]
  def tasks(deltas) do
    deltas
    |> Enum.with_index(1)
    |> Enum.map(fn {delta, index} -> task(delta, index) end)
  end

  @doc """
  The tasks, split by whether the Skill made them better, worse or no different.
  """
  @spec by_outcome([task()]) :: %{outcome() => [task()]}
  def by_outcome(tasks) do
    Map.merge(%{better: [], worse: [], same: []}, Enum.group_by(tasks, & &1.outcome))
  end

  @doc """
  One task of each kind the Result has, in the order better, worse, same.
  """
  @spec examples(%{outcome() => [task()]}) :: [task()]
  def examples(groups) do
    for outcome <- [:better, :worse, :same], task <- Enum.take(groups[outcome], 1), do: task
  end

  @doc """
  Whether every check this site ran on the Result's files passed.
  """
  @spec files_verified?(PublicationEntry.t()) :: boolean()
  def files_verified?(%{verification_checks_run: run, verification_checks_passed: passed}),
    do: run > 0 and passed == run

  @doc """
  Whether the numbers are signed by the key of the person who ran both runs.
  """
  @spec reported_by_runner?(PublicationEntry.t()) :: boolean()
  def reported_by_runner?(%{participant_kind: kind}), do: kind == :local_ed25519

  @doc """
  What the signed report found differed between the two runs' settings, and
  whether that was only what the Climb allows to differ.
  """
  @spec skill_change(PublicationEntry.t()) :: %{
          controlled?: boolean(),
          differences: [%{place: String.t(), without: value(), with: value()}]
        }
  def skill_change(%{submission_bytes: bytes}) do
    %{"controlled" => controlled, "differences" => differences} =
      Bundle.stored_report!(bytes)["manifest_comparison"]

    %{controlled?: controlled, differences: Enum.map(differences, &difference/1)}
  end

  @doc """
  A score as a reader reads it: a share for rewards between 0 and 1.
  """
  @spec score(number()) :: String.t()
  def score(value) when value >= 0 and value <= 1, do: "#{Float.round(value * 100.0, 1)}%"
  def score(value), do: number(value)

  @doc """
  The change in the mean score, in percentage points for rewards between 0 and 1.
  """
  @spec mean_change(PublicationEntry.t()) :: String.t()
  def mean_change(%{baseline_mean: baseline, candidate_mean: candidate, absolute_delta: delta})
      when baseline >= 0 and baseline <= 1 and candidate >= 0 and candidate <= 1 do
    signed_points(delta) <> " percentage points"
  end

  def mean_change(%{absolute_delta: delta}), do: signed(delta)

  @doc """
  A digest cut to a length a reader can compare by eye.
  """
  @spec short_digest(String.t()) :: String.t()
  def short_digest("sha256:" <> digest), do: "sha256:" <> String.slice(digest, 0, 10) <> "…"
  def short_digest(digest), do: digest

  # -- Internals ------------------------------------------------------------

  defp task(delta, index) do
    baseline = delta["baseline_reward"]
    candidate = delta["candidate_reward"]

    %{
      hash: delta["task_hash"],
      label: "Task " <> String.pad_leading(Integer.to_string(index), 2, "0"),
      short_hash: short_digest(delta["task_hash"]),
      baseline: score(baseline),
      candidate: score(candidate),
      delta: task_change(candidate - baseline, baseline, candidate),
      outcome: outcome(candidate, baseline)
    }
  end

  defp outcome(candidate, baseline) when candidate > baseline, do: :better
  defp outcome(candidate, baseline) when candidate < baseline, do: :worse
  defp outcome(_candidate, _baseline), do: :same

  defp task_change(delta, baseline, candidate)
       when baseline >= 0 and baseline <= 1 and candidate >= 0 and candidate <= 1,
       do: signed_points(delta) <> " pts"

  defp task_change(delta, _baseline, _candidate), do: signed(delta)

  defp signed_points(delta) do
    points = Float.round(delta * 100.0, 1)
    if points > 0, do: "+#{points}", else: "#{points}"
  end

  defp signed(value) do
    rounded = value |> Kernel./(1) |> Float.round(3)
    if rounded > 0, do: "+#{rounded}", else: to_string(rounded)
  end

  defp number(value) when is_integer(value), do: to_string(value)
  defp number(value) when is_float(value), do: value |> Float.round(3) |> to_string()

  defp difference(%{"pointer" => pointer, "baseline" => baseline, "candidate" => candidate}) do
    whole_skill? = whole_skill?(pointer)

    %{
      place: place(pointer),
      without: value(baseline, whole_skill?),
      with: value(candidate, whole_skill?)
    }
  end

  defp whole_skill?(@skill_pointer <> rest), do: not String.contains?(rest, "/")
  defp whole_skill?(_pointer), do: false

  defp place(@skill_pointer <> rest) do
    case String.split(rest, "/") do
      [index] -> skill_label(index)
      [index, field] -> skill_label(index) <> " " <> field_words(field)
    end
  end

  defp place(pointer), do: pointer

  defp skill_label(index), do: "Skill #{String.to_integer(index) + 1}"

  defp field_words("digest"), do: "fingerprint"
  defp field_words("size"), do: "size"
  defp field_words("media_type"), do: "file type"
  defp field_words("relative_path"), do: "file name"

  defp value(nil, true), do: :no_skill
  defp value(nil, false), do: :not_set
  defp value(%{"digest" => digest, "size" => size}, true), do: {:artifact, digest, size}
  defp value(text, _whole_skill?) when is_binary(text), do: {:text, text}
  defp value(other, _whole_skill?), do: {:text, Jason.encode!(other)}
end
