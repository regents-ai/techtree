defmodule Techtree.Network.Result do
  @moduledoc """
  A signed result, worked out again by this site from the task rows it carries
  and the rule its Campaign set before either run.

  The CLI writes the two means, the change between them and a decision into
  the report it signs. A signature says who wrote those figures, not that they
  are right, so none of them is taken on trust. The means and the change are
  recomputed here from the per-task scores, exactly: every score is read as
  the decimal number the report writes, and nothing is added or compared in
  binary floating point. The decision is recomputed by the rule the CLI applies
  (`decide_uplift` in `techtree.receipts.uplift`), from the Campaign this site
  publishes. A report whose figures or decision are not the ones its own rows
  and its Campaign give is refused.

  Three things are mirrored from the CLI rather than invented here.

    * **The grade.** A report that is not graded P1 withholds its decision and
      says `development_only`. One that is graded P1 has a valid score and a
      controlled comparison, because the CLI grades no other report P1, and its
      decision is the Campaign's rule applied to the change.
    * **The rule.** No decision is possible when the Campaign neither requires
      the Skill to score higher nor sets a minimum change. Otherwise the change
      is turned down when the Campaign requires a rise and there is none, or
      when it falls short of the minimum, and it is accepted when it clears
      both.
    * **The one caveat.** A comparison is "controlled with warnings" exactly
      when the Campaign's model names no build, because the provider publishes
      none. That is the only warning the CLI records.

  The CLI does its arithmetic in binary floating point, so its written means
  can differ from the exact ones around the sixteenth significant digit. A
  written figure is accepted when it is within a billionth of the scores' own
  size of the exact one; anything further is a different number. The decision
  has no such allowance. Exactly at the Campaign's minimum this site and a
  binary calculation can disagree, and then the result is refused rather than
  published under a decision this site would not reach.

  One reading is this site's own. The decision "rejected" covers both "no
  better" and "worse", and a page has to say which. A change is called a
  regression only by the mirror of the acceptance rule: the Skill scored lower,
  by at least the Campaign's minimum.

  The Skill change is read the same way: the report's comparison of the two
  runs' settings must be controlled, and every difference in it must be a Skill
  the Campaign lets differ, written in the shape the CLI writes one.
  """

  alias Techtree.Catalog.Digest
  alias Techtree.Network.Error

  @grades ~w(P1 development_only)
  @decisions ~w(accepted rejected inconclusive invalid development_only)
  @comparison_statuses ~w(pending controlled controlled_with_warnings invalid development_only)
  @score_statuses ~w(pending valid invalid errored missing development_only)
  @controlled ~w(controlled controlled_with_warnings)

  @skill_pointer "/agents/subject/harness/skills/"
  @skill_fields ~w(digest media_type size relative_path)
  @skill_reference_keys ~w(digest media_type relative_path size)

  # Wide enough that adding and multiplying scores written as JSON numbers never
  # rounds: a double spans about 650 decimal digits from end to end.
  @exact %Decimal.Context{precision: 1_000}

  @tolerance Decimal.new("1e-9")

  defstruct [
    :baseline_mean,
    :candidate_mean,
    :absolute_delta,
    :minimum,
    :wins,
    :losses,
    :ties,
    :decision,
    :verdict,
    :why,
    :model_build_unproven?
  ]

  @typedoc """
  Why the verdict is what it is, for a page to put into words.
  """
  @type why ::
          :cleared_rule
          | :worse_past_rule
          | {:short_of_rule, :higher | :same | :lower}
          | :no_rule
          | {:score_not_valid, String.t()}
          | :not_controlled
          | :not_sealed

  @type t :: %__MODULE__{
          baseline_mean: Decimal.t(),
          candidate_mean: Decimal.t(),
          absolute_delta: Decimal.t(),
          minimum: Decimal.t(),
          wins: non_neg_integer(),
          losses: non_neg_integer(),
          ties: non_neg_integer(),
          decision: String.t(),
          verdict: :improved | :regressed | :not_enough_evidence,
          why: why(),
          model_build_unproven?: boolean()
        }

  @typedoc """
  One side of one Skill difference: no Skill, a whole Skill by fingerprint and
  size, or one field of a Skill.
  """
  @type value ::
          :none
          | :not_set
          | {:skill, String.t(), pos_integer()}
          | {:digest, String.t()}
          | {:size, pos_integer()}
          | {:text, String.t()}

  @type change :: %{
          skill: non_neg_integer(),
          field: String.t() | nil,
          without: value(),
          with: value()
        }

  @doc """
  Recompute a report's result under its Campaign, or name what does not hold.
  """
  @spec assess(map(), map()) :: {:ok, t()} | {:error, Error.t()}
  def assess(report, campaign) when is_map(report) and is_map(campaign) do
    Decimal.Context.with(@exact, fn ->
      with {:ok, rows} <- rows(report["task_deltas"]),
           {:ok, written} <- written(report["primary_result"], campaign),
           {:ok, statuses} <- statuses(report["statuses"]),
           {:ok, grade} <- grade(report["proof_grade"]),
           {:ok, decision} <- decision(report["decision"]),
           tally = tally(rows),
           :ok <- counts_agree(tally, written),
           :ok <- figures_agree(tally, written),
           :ok <- statuses_agree(grade, statuses, campaign),
           rule = rule(campaign),
           :ok <- decision_agrees(decision, expected_decision(grade, rule, tally)) do
        {:ok, result(decision, rule, tally, statuses)}
      end
    end)
  end

  @doc """
  What the report says differed between the two runs' settings: only Skills
  the Campaign lets differ, each side said as a value a page can show.
  """
  @spec skill_change(map(), map()) :: {:ok, [change()]} | {:error, Error.t()}
  def skill_change(
        %{
          "manifest_comparison" => %{
            "controlled" => true,
            "violations" => [],
            "differences" => [_ | _] = differences
          }
        },
        %{"mutation_contract" => %{"maximum_skills" => maximum}}
      ) do
    differences
    |> Enum.reduce_while({:ok, []}, fn difference, {:ok, changes} ->
      case change(difference, maximum) do
        {:ok, change} -> {:cont, {:ok, [change | changes]}}
        :error -> {:halt, invalid_change(difference)}
      end
    end)
    |> case do
      {:ok, changes} -> {:ok, Enum.reverse(changes)}
      error -> error
    end
  end

  def skill_change(_report, _campaign) do
    {:error,
     Error.new(
       :submission_skill_change_invalid,
       "this result does not show its two runs as differing only in a Skill",
       %{}
     )}
  end

  # -- The task rows ---------------------------------------------------------

  defp rows([_ | _] = deltas) do
    if Enum.all?(deltas, &scored?/1) do
      {:ok,
       Enum.map(deltas, fn delta ->
         %{baseline: exact(delta["baseline_reward"]), candidate: exact(delta["candidate_reward"])}
       end)}
    else
      inconsistent("every task in this result carries a score for each run", %{})
    end
  end

  defp rows(_deltas), do: inconsistent("this result scores no tasks", %{})

  defp scored?(%{
         "task_hash" => hash,
         "baseline_reward" => baseline,
         "candidate_reward" => candidate
       }),
       do: is_binary(hash) and is_number(baseline) and is_number(candidate)

  defp scored?(_delta), do: false

  defp written(
         %{
           "reward_name" => reward,
           "baseline_mean" => baseline,
           "candidate_mean" => candidate,
           "absolute_delta" => delta,
           "wins" => wins,
           "losses" => losses,
           "ties" => ties
         },
         %{"scoring" => %{"primary_reward" => reward}}
       )
       when is_number(baseline) and is_number(candidate) and is_number(delta) and
              is_integer(wins) and is_integer(losses) and is_integer(ties) do
    {:ok,
     %{
       baseline: exact(baseline),
       candidate: exact(candidate),
       delta: exact(delta),
       wins: wins,
       losses: losses,
       ties: ties
     }}
  end

  defp written(_result, _campaign) do
    inconsistent(
      "this result does not state its means, their change and its counts for the " <>
        "score its Campaign decides on",
      %{}
    )
  end

  defp statuses(%{"comparison" => comparison, "score" => score})
       when comparison in @comparison_statuses and score in @score_statuses,
       do: {:ok, %{comparison: comparison, score: score}}

  defp statuses(_statuses),
    do: inconsistent("this result does not state its score and comparison in known words", %{})

  defp grade(grade) when grade in @grades, do: {:ok, grade}

  defp grade(grade),
    do: inconsistent("this result's grade is not one this site knows", %{"proof_grade" => grade})

  defp decision(decision) when decision in @decisions, do: {:ok, decision}

  defp decision(decision),
    do:
      inconsistent("this result's decision is not one this site knows", %{"decision" => decision})

  defp exact(number) when is_integer(number), do: Decimal.new(number)
  defp exact(number) when is_float(number), do: Decimal.from_float(number)

  # -- The recomputation -----------------------------------------------------

  defp tally(rows) do
    %{
      tasks: length(rows),
      baseline: sum(rows, :baseline),
      candidate: sum(rows, :candidate),
      scale: Enum.reduce(rows, Decimal.new(1), &largest/2),
      wins: Enum.count(rows, &(Decimal.compare(&1.candidate, &1.baseline) == :gt)),
      losses: Enum.count(rows, &(Decimal.compare(&1.candidate, &1.baseline) == :lt)),
      ties: Enum.count(rows, &(Decimal.compare(&1.candidate, &1.baseline) == :eq))
    }
  end

  defp sum(rows, side),
    do: Enum.reduce(rows, Decimal.new(0), &Decimal.add(Map.fetch!(&1, side), &2))

  defp largest(row, scale),
    do: scale |> Decimal.max(Decimal.abs(row.baseline)) |> Decimal.max(Decimal.abs(row.candidate))

  # The change in the mean, times the number of tasks: the difference of the
  # two sums, which stays exact where the mean itself would not.
  defp gap(tally), do: Decimal.sub(tally.candidate, tally.baseline)

  defp counts_agree(tally, written) do
    recounted = Map.take(tally, [:wins, :losses, :ties])

    if recounted == Map.take(written, [:wins, :losses, :ties]) do
      :ok
    else
      inconsistent(
        "the wins, losses and ties in this result do not recompute from its own tasks",
        %{"recomputed" => Map.new(recounted, fn {key, count} -> {to_string(key), count} end)}
      )
    end
  end

  # Each written figure, times the number of tasks, against the exact sum it
  # stands for, so no division happens on the way to the comparison.
  defp figures_agree(tally, written) do
    allowance = @tolerance |> Decimal.mult(tally.scale) |> Decimal.mult(tally.tasks)

    [
      {"baseline_mean", written.baseline, tally.baseline},
      {"candidate_mean", written.candidate, tally.candidate},
      {"absolute_delta", written.delta, gap(tally)}
    ]
    |> Enum.find(fn {_field, figure, total} ->
      figure
      |> Decimal.mult(tally.tasks)
      |> Decimal.sub(total)
      |> Decimal.abs()
      |> Decimal.gt?(allowance)
    end)
    |> case do
      nil ->
        :ok

      {field, figure, total} ->
        inconsistent(
          "a figure in this result is not the one its own tasks give",
          %{
            "field" => field,
            "written" => Decimal.to_string(figure, :normal),
            "recomputed" =>
              total |> Decimal.div(tally.tasks) |> Decimal.round(17) |> Decimal.to_string(:normal)
          }
        )
    end
  end

  defp statuses_agree("P1", %{comparison: comparison, score: score}, _campaign)
       when comparison not in @controlled or score != "valid" do
    inconsistent(
      "this result is graded to make a call, and its own score or comparison says it cannot",
      %{"comparison" => comparison, "score" => score}
    )
  end

  defp statuses_agree(_grade, %{comparison: comparison}, campaign)
       when comparison in @controlled do
    pinned? = is_binary(get_in(campaign, ["agents", "subject", "model", "revision"]))

    if comparison == "controlled" == pinned? do
      :ok
    else
      inconsistent(
        "this result's comparison warns about the model build exactly when its Campaign " <>
          "names none, and this one does not",
        %{"comparison" => comparison}
      )
    end
  end

  defp statuses_agree(_grade, _statuses, _campaign), do: :ok

  defp rule(%{
         "scoring" => %{
           "require_candidate_above_baseline" => require_above?,
           "minimum_absolute_delta" => minimum
         }
       }),
       do: %{require_above?: require_above?, minimum: exact(minimum)}

  # `decide_uplift`, over the exact sums. The change clears the minimum when
  # the gap between the sums clears the minimum times the number of tasks.
  defp expected_decision("development_only", _rule, _tally), do: "development_only"

  defp expected_decision("P1", rule, tally) do
    gap = gap(tally)

    cond do
      not rule.require_above? and Decimal.eq?(rule.minimum, 0) -> "inconclusive"
      rule.require_above? and not Decimal.gt?(gap, 0) -> "rejected"
      Decimal.lt?(gap, Decimal.mult(rule.minimum, tally.tasks)) -> "rejected"
      true -> "accepted"
    end
  end

  defp decision_agrees(decision, decision), do: :ok

  defp decision_agrees(written, expected) do
    inconsistent(
      "this result's decision is not the one the rule its Campaign set gives for its own tasks",
      %{"decision" => written, "recomputed" => expected}
    )
  end

  defp result(decision, rule, tally, statuses) do
    {verdict, why} = verdict(decision, rule, tally, statuses)

    %__MODULE__{
      baseline_mean: Decimal.div(tally.baseline, tally.tasks),
      candidate_mean: Decimal.div(tally.candidate, tally.tasks),
      absolute_delta: Decimal.div(gap(tally), tally.tasks),
      minimum: rule.minimum,
      wins: tally.wins,
      losses: tally.losses,
      ties: tally.ties,
      decision: decision,
      verdict: verdict,
      why: why,
      model_build_unproven?: statuses.comparison == "controlled_with_warnings"
    }
  end

  defp verdict("accepted", _rule, _tally, _statuses), do: {:improved, :cleared_rule}

  defp verdict("rejected", rule, tally, _statuses) do
    gap = gap(tally)

    cond do
      Decimal.lt?(gap, 0) and
          not Decimal.lt?(Decimal.negate(gap), Decimal.mult(rule.minimum, tally.tasks)) ->
        {:regressed, :worse_past_rule}

      Decimal.gt?(gap, 0) ->
        {:not_enough_evidence, {:short_of_rule, :higher}}

      Decimal.eq?(gap, 0) ->
        {:not_enough_evidence, {:short_of_rule, :same}}

      true ->
        {:not_enough_evidence, {:short_of_rule, :lower}}
    end
  end

  defp verdict("inconclusive", _rule, _tally, _statuses), do: {:not_enough_evidence, :no_rule}

  defp verdict("development_only", _rule, _tally, %{score: score}) when score != "valid",
    do: {:not_enough_evidence, {:score_not_valid, score}}

  defp verdict("development_only", _rule, _tally, %{comparison: comparison})
       when comparison not in @controlled,
       do: {:not_enough_evidence, :not_controlled}

  defp verdict("development_only", _rule, _tally, _statuses),
    do: {:not_enough_evidence, :not_sealed}

  defp inconsistent(sentence, details),
    do: {:error, Error.new(:submission_result_inconsistent, sentence, details)}

  # -- The Skill change ------------------------------------------------------

  defp change(
         %{"pointer" => @skill_pointer <> place, "baseline" => baseline, "candidate" => candidate} =
           difference,
         maximum
       )
       when map_size(difference) == 3 do
    with {:ok, skill, field} <- place(place, maximum),
         {:ok, without} <- value(field, baseline),
         {:ok, with_skill} <- value(field, candidate) do
      {:ok, %{skill: skill, field: field, without: without, with: with_skill}}
    end
  end

  defp change(_difference, _maximum), do: :error

  defp place(place, maximum) do
    case String.split(place, "/") do
      [index] -> skill(index, maximum, nil)
      [index, field] when field in @skill_fields -> skill(index, maximum, field)
      _other -> :error
    end
  end

  defp skill(index, maximum, field) do
    if String.match?(index, ~r/\A(0|[1-9][0-9]*)\z/) and String.to_integer(index) < maximum,
      do: {:ok, String.to_integer(index), field},
      else: :error
  end

  defp value(nil, nil), do: {:ok, :none}

  defp value(nil, %{"digest" => digest, "media_type" => media_type, "size" => size} = reference) do
    if Enum.all?(Map.keys(reference), &(&1 in @skill_reference_keys)) and Digest.valid?(digest) and
         text?(media_type) and positive?(size) and optional_text?(reference["relative_path"]),
       do: {:ok, {:skill, digest, size}},
       else: :error
  end

  defp value("digest", digest) when is_binary(digest),
    do: if(Digest.valid?(digest), do: {:ok, {:digest, digest}}, else: :error)

  defp value("size", size), do: if(positive?(size), do: {:ok, {:size, size}}, else: :error)
  defp value("media_type", text), do: if(text?(text), do: {:ok, {:text, text}}, else: :error)
  defp value("relative_path", nil), do: {:ok, :not_set}
  defp value("relative_path", text), do: if(text?(text), do: {:ok, {:text, text}}, else: :error)
  defp value(_field, _value), do: :error

  defp text?(value), do: is_binary(value) and value != ""
  defp optional_text?(value), do: is_nil(value) or text?(value)
  defp positive?(value), do: is_integer(value) and value > 0

  defp invalid_change(difference) do
    {:error,
     Error.new(
       :submission_skill_change_invalid,
       "a difference this result names between its two runs is not a Skill its Campaign " <>
         "lets differ, written the way the CLI writes one",
       %{"pointer" => pointer(difference)}
     )}
  end

  defp pointer(%{"pointer" => pointer}) when is_binary(pointer), do: pointer
  defp pointer(_difference), do: nil
end
