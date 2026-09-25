defmodule TechtreeWeb.ResultAssessment do
  @moduledoc """
  How one published Result reads on its page: the verdict in words, the tasks
  by name and score, and the Skill change as values a reader can compare.

  Nothing here decides anything. The verdict and the reason for it come from
  `Techtree.Network.Result`, which recomputed them from the Result's own task
  scores and its Campaign's rule before the Result was published, and does the
  same over the stored bytes when the page is read. This module only puts them
  into words.

  Tasks are named by their place in the Campaign's committed order and their
  fingerprint, because that is all a published Result holds about a task. It
  keeps neither the task's words nor the agent's answers.

  Every number is shown from its exact decimal value, so a change that is zero
  reads as zero and a change that is not never rounds into the wrong sign.
  """

  alias Techtree.Network.Result

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
  The verdict as the page's heading says it.
  """
  @spec verdict_label(Result.t()) :: String.t()
  def verdict_label(%Result{verdict: :improved}), do: "Improved"
  def verdict_label(%Result{verdict: :regressed}), do: "Regressed"
  def verdict_label(%Result{verdict: :not_enough_evidence}), do: "Not enough evidence"

  @doc """
  Why the verdict is what it is, in one or two sentences, naming the smallest
  change the Climb's rule accepts where that is the reason.
  """
  @spec reason(Result.t()) :: String.t()
  def reason(%Result{why: :cleared_rule}) do
    "With the Skill, the agent scored higher, and the result clears the rule this Climb set " <>
      "before either run."
  end

  def reason(%Result{why: :worse_past_rule, minimum: minimum} = result) do
    if Decimal.eq?(minimum, 0) do
      "With the Skill, the agent scored lower overall."
    else
      "With the Skill, the agent scored lower overall, by at least the " <>
        amount(result, minimum) <> " this Climb asks of an improvement."
    end
  end

  def reason(%Result{why: {:short_of_rule, :higher}, minimum: minimum} = result) do
    "With the Skill, the agent scored higher, but by less than the " <>
      amount(result, minimum) <> " this Climb set before either run."
  end

  def reason(%Result{why: {:short_of_rule, :same}}) do
    "With and without the Skill, the agent scored exactly the same overall."
  end

  def reason(%Result{why: {:short_of_rule, :lower}, minimum: minimum} = result) do
    "With the Skill, the agent scored lower, but by less than the " <>
      amount(result, minimum) <>
      " this Climb set before either run, so it is not shown to be worse either."
  end

  def reason(%Result{why: :no_rule}) do
    "This Climb set no rule before the runs that could decide between them."
  end

  def reason(%Result{why: {:score_not_valid, status}}) do
    "The run's scores #{score_status_words(status)}, so its own report makes no call."
  end

  def reason(%Result{why: :not_controlled}) do
    "The run did not show that its two sides differed only in the Skill, so its own report " <>
      "makes no call."
  end

  def reason(%Result{why: :not_sealed}) do
    "When the run wrote its report, its evidence did not meet every condition for making a " <>
      "call, so the report makes no call."
  end

  @doc """
  The change in the mean score: in percentage points when both means are
  shares between 0 and 1, and as a plain signed number otherwise.
  """
  @spec mean_change(Result.t()) :: String.t()
  def mean_change(%Result{absolute_delta: delta} = result) do
    if shares?(result), do: points(delta) <> " percentage points", else: signed(delta)
  end

  @doc """
  One mean score as a reader reads it.
  """
  @spec mean(Result.t(), :baseline_mean | :candidate_mean) :: String.t()
  def mean(%Result{} = result, side), do: score(Map.fetch!(result, side))

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
  @spec change_label(Result.change(), boolean()) :: String.t()
  def change_label(%{skill: skill, field: field}, one_skill?) do
    name = if one_skill?, do: "The Skill", else: "Skill #{skill + 1}"

    case field do
      nil -> name
      field -> name <> "'s " <> field_words(field)
    end
  end

  @doc """
  The fingerprint of the Skill the run used, as the preparation step prints it,
  when the Skill change names one.
  """
  @spec skill_fingerprint([Result.change()]) :: String.t() | nil
  def skill_fingerprint(changes) do
    Enum.find_value(changes, fn
      %{field: nil, with: {:skill, digest, _size}} -> digest
      %{field: "digest", with: {:digest, digest}} -> digest
      _change -> nil
    end)
  end

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
      baseline: score(baseline),
      candidate: score(candidate),
      delta: task_change(baseline, candidate),
      outcome: outcome(Decimal.compare(candidate, baseline))
    }
  end

  defp outcome(:gt), do: :better
  defp outcome(:lt), do: :worse
  defp outcome(:eq), do: :same

  defp task_change(baseline, candidate) do
    change = Decimal.sub(candidate, baseline)
    if share?(baseline) and share?(candidate), do: points(change) <> " pts", else: signed(change)
  end

  defp amount(result, minimum) do
    if shares?(result), do: plain_points(minimum) <> " percentage points", else: plain(minimum)
  end

  defp shares?(%Result{baseline_mean: baseline, candidate_mean: candidate}),
    do: share?(baseline) and share?(candidate)

  defp share?(value), do: not Decimal.lt?(value, 0) and not Decimal.gt?(value, 1)

  defp score(value) do
    if share?(value),
      do: plain_points(value) <> "%",
      else: plain(value)
  end

  # A change in percentage points, to one place, with its sign. A change too
  # small to show at one place says so rather than rounding to zero.
  defp points(delta) do
    scaled = Decimal.mult(delta, 100)
    rounded = Decimal.round(scaled, 1)

    cond do
      Decimal.eq?(scaled, 0) -> "0.0"
      Decimal.eq?(rounded, 0) and Decimal.gt?(scaled, 0) -> "between 0 and +0.1"
      Decimal.eq?(rounded, 0) -> "between 0 and -0.1"
      Decimal.gt?(rounded, 0) -> "+" <> Decimal.to_string(rounded, :normal)
      true -> Decimal.to_string(rounded, :normal)
    end
  end

  # A share in percent, always to one place, so "25.0" sits beside "47.2".
  defp plain_points(value),
    do: value |> Decimal.mult(100) |> Decimal.round(1) |> Decimal.to_string(:normal)

  defp signed(value) do
    rounded = Decimal.round(value, 3)

    cond do
      Decimal.eq?(value, 0) -> "0"
      Decimal.gt?(value, 0) -> "+" <> text(rounded)
      true -> text(rounded)
    end
  end

  defp plain(value), do: value |> Decimal.round(3) |> text()

  defp text(value), do: value |> Decimal.normalize() |> Decimal.to_string(:normal)

  defp exact(number) when is_integer(number), do: Decimal.new(number)
  defp exact(number) when is_float(number), do: Decimal.from_float(number)

  defp field_words("digest"), do: "fingerprint"
  defp field_words("size"), do: "size"
  defp field_words("media_type"), do: "file type"
  defp field_words("relative_path"), do: "file name"

  defp score_status_words("invalid"), do: "were marked not valid"
  defp score_status_words("errored"), do: "failed with an error"
  defp score_status_words("missing"), do: "are missing"
  defp score_status_words("pending"), do: "were never finished"
  defp score_status_words("development_only"), do: "were marked as practice only"
end
