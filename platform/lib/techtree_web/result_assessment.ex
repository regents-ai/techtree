defmodule TechtreeWeb.ResultAssessment do
  @moduledoc """
  How one published Result reads on its page: the verdict in words, the tasks
  by name and score, and the Skill change as values a reader can compare.

  Nothing here decides anything. The reason for the verdict comes from the
  Result's stored `Techtree.Network.Assessment`, which
  `Techtree.Network.Result` worked out from the Result's own task scores and
  its Campaign's rule when the Result was published. This module only puts it
  into words.

  Tasks are named by their place in the Campaign's committed order and their
  fingerprint, because that is all a published Result holds about a task. It
  keeps neither the task's words nor the agent's answers.

  Every number is rounded to three decimal places from its exact decimal
  value. A value that is zero reads as zero, one too small to show at three
  places says so rather than rounding to zero, and nothing reads as "-0".

  A Campaign names its score and the rule that decides between the two runs,
  and states no unit or range, so a mean that happens to fall between 0 and 1
  is not taken for a share and is never turned into a percentage.
  """

  alias Techtree.Network.Assessment
  alias Techtree.Network.Assessment.SkillChange

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

  @doc """
  The verdict the reason comes to. Only a change that cleared the Campaign's
  rule is an improvement, and only a fall by at least its minimum is a
  regression.
  """
  @spec verdict(Assessment.t()) :: :improved | :regressed | :not_enough_evidence
  def verdict(%Assessment{reason: :cleared_rule}), do: :improved
  def verdict(%Assessment{reason: :fell_past_rule}), do: :regressed
  def verdict(%Assessment{}), do: :not_enough_evidence

  @doc """
  The verdict as the page's heading says it.
  """
  @spec verdict_label(Assessment.t()) :: String.t()
  def verdict_label(assessment) do
    case verdict(assessment) do
      :improved -> "Improved"
      :regressed -> "Regressed"
      :not_enough_evidence -> "Not enough evidence"
    end
  end

  @doc """
  Why the verdict is what it is, in one or two sentences, naming the smallest
  change the Climb's rule accepts where that is the reason.
  """
  @spec reason(Assessment.t()) :: String.t()
  def reason(%Assessment{reason: :cleared_rule}) do
    "With the Skill, the agent scored higher, and the result clears the rule this Climb set " <>
      "before either run."
  end

  def reason(%Assessment{reason: :fell_past_rule, minimum: minimum}) do
    if Decimal.eq?(minimum, 0) do
      "With the Skill, the agent scored lower overall."
    else
      "With the Skill, the agent scored lower overall, by at least the change of " <>
        plain(minimum) <> " this Climb asks of an improvement."
    end
  end

  def reason(%Assessment{reason: :rose_short_of_rule, minimum: minimum}) do
    "With the Skill, the agent scored higher, but by less than the change of " <>
      plain(minimum) <> " this Climb set before either run."
  end

  def reason(%Assessment{reason: :unchanged}) do
    "With and without the Skill, the agent scored exactly the same overall."
  end

  def reason(%Assessment{reason: :fell_short_of_rule, minimum: minimum}) do
    "With the Skill, the agent scored lower, but by less than the change of " <>
      plain(minimum) <>
      " this Climb set before either run, so it is not shown to be worse either."
  end

  def reason(%Assessment{reason: :no_rule}) do
    "This Climb set no rule before the runs that could decide between them."
  end

  @doc """
  The change in the mean score, as a signed number on the score's own scale.
  """
  @spec mean_change(Assessment.t()) :: String.t()
  def mean_change(%Assessment{} = assessment) do
    assessment.candidate_total
    |> Decimal.sub(assessment.baseline_total)
    |> Decimal.div(assessment.task_count)
    |> signed()
  end

  @doc """
  One mean score as a reader reads it.
  """
  @spec mean(Assessment.t(), :baseline | :candidate) :: String.t()
  def mean(%Assessment{} = assessment, side), do: plain(exact_mean(assessment, side))

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
  What one Skill difference is about, in words: the Skill itself, or one of its
  fields. A Climb that lets only one Skill differ calls it "the Skill".
  """
  @spec change_label(SkillChange.t(), boolean()) :: String.t()
  def change_label(%{skill: skill, field: field}, one_skill?) do
    name = if one_skill?, do: "The Skill", else: "Skill #{skill + 1}"

    case field do
      nil -> name
      field -> name <> "'s " <> field_words(field)
    end
  end

  @doc """
  One reward as a reader reads it, the way a task's score reads on a Result's
  page.
  """
  @spec reward(number()) :: String.t()
  def reward(number), do: number |> exact() |> plain()

  @doc """
  The change from one reward to another, the way a task's change reads on a
  Result's page.
  """
  @spec reward_change(number(), number()) :: String.t()
  def reward_change(baseline, candidate), do: task_change(exact(baseline), exact(candidate))

  @doc """
  A change already worked out, such as a Result's change in the mean, the way
  the list of Results shows it.
  """
  @spec change(number()) :: String.t()
  def change(number), do: number |> exact() |> signed()

  @doc """
  A digest cut to a length a reader can compare by eye.
  """
  @spec short_digest(String.t()) :: String.t()
  def short_digest("sha256:" <> digest), do: "sha256:" <> String.slice(digest, 0, 10) <> "…"
  def short_digest(digest), do: digest

  # -- Internals ------------------------------------------------------------

  defp task(delta, index) do
    baseline = exact(delta["baseline_reward"])
    candidate = exact(delta["candidate_reward"])

    %{
      hash: delta["task_hash"],
      label: "Task " <> String.pad_leading(Integer.to_string(index), 2, "0"),
      short_hash: short_digest(delta["task_hash"]),
      baseline: plain(baseline),
      candidate: plain(candidate),
      delta: task_change(baseline, candidate),
      outcome: outcome(Decimal.compare(candidate, baseline))
    }
  end

  defp outcome(:gt), do: :better
  defp outcome(:lt), do: :worse
  defp outcome(:eq), do: :same

  defp task_change(baseline, candidate), do: candidate |> Decimal.sub(baseline) |> signed()

  defp exact_mean(assessment, :baseline),
    do: Decimal.div(assessment.baseline_total, assessment.task_count)

  defp exact_mean(assessment, :candidate),
    do: Decimal.div(assessment.candidate_total, assessment.task_count)

  # A change carries its sign; a score carries only a minus.
  defp signed(value), do: three_places(value, "+")
  defp plain(value), do: three_places(value, "")

  # A value to three places. One too small to show at three places says so
  # rather than rounding to zero, and zero is always "0", never "-0".
  defp three_places(value, plus) do
    rounded = Decimal.round(value, 3)

    cond do
      Decimal.eq?(value, 0) -> "0"
      Decimal.eq?(rounded, 0) and Decimal.gt?(value, 0) -> "between 0 and #{plus}0.001"
      Decimal.eq?(rounded, 0) -> "between 0 and -0.001"
      Decimal.gt?(value, 0) -> plus <> text(rounded)
      true -> text(rounded)
    end
  end

  defp text(value), do: value |> Decimal.normalize() |> Decimal.to_string(:normal)

  # A score as the site read it when the Result was published: a double, then
  # the shortest decimal that reads back as it.
  defp exact(number), do: number |> :erlang.float() |> Decimal.from_float()

  defp field_words("digest"), do: "fingerprint"
  defp field_words("size"), do: "size"
  defp field_words("media_type"), do: "file type"
  defp field_words("relative_path"), do: "file name"
end
