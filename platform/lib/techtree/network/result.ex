defmodule Techtree.Network.Result do
  @moduledoc """
  A signed result, worked out again by this site from the task rows it carries
  and the rule its Campaign set before either run.

  The CLI writes the two means, the change between them, the wins, losses and
  ties, and a decision into the report it signs. A signature says who wrote
  them, not that they are right. This site counts the wins, losses and ties
  again and decides again by the Campaign this site publishes, and a report
  whose counts or decision are not the ones its own rows give is refused. The
  written means and change are not compared: they are the CLI's rounding of
  the same numbers into binary floating point, and a page shows this site's
  exact ones instead.

  Both sides do the arithmetic the same way, so they cannot disagree at the
  Campaign's minimum. Every score is read as a double, the way a JSON reader
  reads any number, integers included, and then as the shortest decimal that
  reads back as that double, which is the decimal the JSON text carries. The
  CLI reads each score through `repr` for the same decimal (`decide_uplift` in
  `techtree.receipts.uplift`). The sums are then exact, and the rule compares
  the difference between the two sums with the minimum times the number of
  tasks, so nothing is divided before the decision.

  Three things are mirrored from the CLI rather than invented here.

    * **What can be published.** The CLI publishes only a report graded P1,
      and grades P1 only a report whose comparison is controlled and whose
      score is valid. Anything else is refused.
    * **The rule.** No decision is possible when the Campaign neither requires
      the Skill to score higher nor sets a minimum change. Otherwise the change
      is turned down when the Campaign requires a rise and there is none, or
      when it falls short of the minimum, and it is accepted when it clears
      both.
    * **The one caveat.** A comparison is "controlled with warnings" exactly
      when the Campaign's model names no build, because the provider publishes
      none. That is the only warning the CLI records.

  One reading is this site's own. The decision "rejected" covers both "no
  better" and "worse", and a page has to say which. A change is called a
  regression only by the mirror of the acceptance rule: the Skill scored lower,
  by at least the Campaign's minimum.

  The Skill change is read the same way: the report's comparison of the two
  runs' settings must be controlled, every difference in it must be a Skill at
  the one place the Campaign lets differ, written in the shape the CLI writes
  one, and every fingerprint it gives the candidate's Skill must be the one
  the candidate run's own settings, carried in the bundle, give it.
  """

  alias Techtree.Catalog.Digest
  alias Techtree.Network.Error

  @decisions ~w(accepted rejected inconclusive)
  @controlled ~w(controlled controlled_with_warnings)

  @skill_fields ~w(digest media_type size relative_path)
  @skill_reference_keys ~w(digest media_type relative_path size)

  # Wide enough that adding and multiplying scores written as JSON numbers never
  # rounds: a double spans about 650 decimal digits from end to end.
  @exact %Decimal.Context{precision: 1_000}

  @typedoc """
  Why the verdict is what it is, for a page to put into words.
  """
  @type reason ::
          :cleared_rule
          | :fell_past_rule
          | :rose_short_of_rule
          | :unchanged
          | :fell_short_of_rule
          | :no_rule

  @typedoc """
  The result as this site recomputed it: the fields of an
  `Techtree.Network.Assessment` other than the Skill change.
  """
  @type t :: %{
          reason: reason(),
          baseline_total: Decimal.t(),
          candidate_total: Decimal.t(),
          task_count: pos_integer(),
          minimum: Decimal.t(),
          wins: non_neg_integer(),
          losses: non_neg_integer(),
          ties: non_neg_integer(),
          model_build_unproven: boolean()
        }

  @typedoc """
  One side of one Skill difference, in the shape of an
  `Techtree.Network.Assessment.SkillValue`.
  """
  @type value ::
          %{kind: :none | :not_set}
          | %{kind: :skill, digest: String.t(), size: pos_integer()}
          | %{kind: :digest, digest: String.t()}
          | %{kind: :size, size: pos_integer()}
          | %{kind: :text, text: String.t()}

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
           :ok <- reportable(report),
           {:ok, decision} <- decision(report["decision"]),
           :ok <- model_build_agrees(report["statuses"], campaign),
           rule = rule(campaign),
           tally = tally(rows),
           :ok <- counts_agree(tally, written),
           :ok <- decision_agrees(decision, expected_decision(rule, tally)) do
        {:ok, result(decision, rule, tally, report["statuses"])}
      end
    end)
  end

  @doc """
  What the report says differed between the two runs' settings: only Skills at
  the place the Campaign lets differ, each side said as a value a page can
  show, and each fingerprint given to the candidate's Skill the one its own
  settings give it.

  `candidate_skills` is the Skill list of the candidate run's settings, read
  from the bundle.
  """
  @spec skill_change(map(), map(), [map()]) :: {:ok, [change()]} | {:error, Error.t()}
  def skill_change(
        %{
          "manifest_comparison" => %{
            "controlled" => true,
            "violations" => [],
            "differences" => [_ | _] = differences
          }
        },
        %{
          "mutation_contract" => %{
            "allowed_differences" => [allowed],
            "maximum_skills" => maximum
          }
        },
        candidate_skills
      )
      when is_binary(allowed) and is_list(candidate_skills) do
    differences
    |> Enum.reduce_while({:ok, []}, fn difference, {:ok, changes} ->
      case change(difference, allowed <> "/", maximum, candidate_skills) do
        {:ok, change} -> {:cont, {:ok, [change | changes]}}
        {:error, _error} = error -> {:halt, error}
      end
    end)
    |> case do
      {:ok, changes} -> {:ok, Enum.reverse(changes)}
      error -> error
    end
  end

  def skill_change(_report, _campaign, _candidate_skills) do
    {:error,
     Error.new(
       :submission_skill_change_invalid,
       "this result does not show its two runs as differing only in a Skill",
       %{}
     )}
  end

  # -- The task rows ---------------------------------------------------------

  defp rows([_ | _] = deltas) do
    rows = Enum.map(deltas, &row/1)

    if Enum.all?(rows, &match?({:ok, _row}, &1)) do
      {:ok, Enum.map(rows, fn {:ok, row} -> row end)}
    else
      inconsistent("every task in this result carries a score for each run", %{})
    end
  end

  defp rows(_deltas), do: inconsistent("this result scores no tasks", %{})

  defp row(%{"task_hash" => hash, "baseline_reward" => baseline, "candidate_reward" => candidate})
       when is_binary(hash) do
    with {:ok, baseline} <- exact(baseline),
         {:ok, candidate} <- exact(candidate) do
      {:ok, %{baseline: baseline, candidate: candidate}}
    end
  end

  defp row(_delta), do: :error

  defp written(
         %{"reward_name" => reward, "wins" => wins, "losses" => losses, "ties" => ties},
         %{"scoring" => %{"primary_reward" => reward}}
       )
       when is_integer(wins) and is_integer(losses) and is_integer(ties),
       do: {:ok, %{wins: wins, losses: losses, ties: ties}}

  defp written(_result, _campaign) do
    inconsistent(
      "this result does not state its counts for the score its Campaign decides on",
      %{}
    )
  end

  defp reportable(%{
         "proof_grade" => "P1",
         "statuses" => %{"comparison" => comparison, "score" => "valid"}
       })
       when comparison in @controlled,
       do: :ok

  defp reportable(report) do
    inconsistent(
      "only a controlled comparison with a valid score, graded P1, can be published, " <>
        "and this result is not one",
      Map.take(report, ["proof_grade", "statuses"])
    )
  end

  defp decision(decision) when decision in @decisions, do: {:ok, decision}

  defp decision(decision),
    do:
      inconsistent("this result's decision is not one this site knows", %{"decision" => decision})

  defp model_build_agrees(%{"comparison" => comparison}, campaign) do
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

  # A number as a JSON reader reads it, a double, then as the shortest decimal
  # that reads back as that double. An integer too large for a double is not a
  # score any report could carry.
  defp exact(number) when is_float(number), do: {:ok, Decimal.from_float(number)}

  defp exact(number) when is_integer(number) do
    {:ok, number |> :erlang.float() |> Decimal.from_float()}
  rescue
    ArgumentError -> :error
  end

  defp exact(_value), do: :error

  # -- The recomputation -----------------------------------------------------

  # The Campaign is one this site publishes, and its import required both.
  defp rule(%{
         "scoring" => %{
           "require_candidate_above_baseline" => require_above?,
           "minimum_absolute_delta" => minimum
         }
       }) do
    {:ok, minimum} = exact(minimum)
    %{require_above?: require_above?, minimum: minimum}
  end

  defp tally(rows) do
    %{
      tasks: length(rows),
      baseline: sum(rows, :baseline),
      candidate: sum(rows, :candidate),
      wins: Enum.count(rows, &(Decimal.compare(&1.candidate, &1.baseline) == :gt)),
      losses: Enum.count(rows, &(Decimal.compare(&1.candidate, &1.baseline) == :lt)),
      ties: Enum.count(rows, &(Decimal.compare(&1.candidate, &1.baseline) == :eq))
    }
  end

  defp sum(rows, side),
    do: Enum.reduce(rows, Decimal.new(0), &Decimal.add(Map.fetch!(&1, side), &2))

  # The change in the mean, times the number of tasks: the difference of the
  # two sums, which stays exact where the mean itself would not.
  defp gap(tally), do: Decimal.sub(tally.candidate, tally.baseline)

  # The minimum change in the mean, times the number of tasks.
  defp required(rule, tally), do: Decimal.mult(rule.minimum, tally.tasks)

  defp counts_agree(tally, written) do
    recounted = Map.take(tally, [:wins, :losses, :ties])

    if recounted == written do
      :ok
    else
      inconsistent(
        "the wins, losses and ties in this result do not recompute from its own tasks",
        %{"recomputed" => Map.new(recounted, fn {key, count} -> {to_string(key), count} end)}
      )
    end
  end

  # `decide_uplift`, over the exact sums.
  defp expected_decision(rule, tally) do
    gap = gap(tally)

    cond do
      not rule.require_above? and Decimal.eq?(rule.minimum, 0) -> "inconclusive"
      rule.require_above? and not Decimal.gt?(gap, 0) -> "rejected"
      Decimal.lt?(gap, required(rule, tally)) -> "rejected"
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

  defp result(decision, rule, tally, %{"comparison" => comparison}) do
    %{
      reason: reason(decision, rule, tally),
      baseline_total: tally.baseline,
      candidate_total: tally.candidate,
      task_count: tally.tasks,
      minimum: rule.minimum,
      wins: tally.wins,
      losses: tally.losses,
      ties: tally.ties,
      model_build_unproven: comparison == "controlled_with_warnings"
    }
  end

  defp reason("accepted", _rule, _tally), do: :cleared_rule
  defp reason("inconclusive", _rule, _tally), do: :no_rule

  defp reason("rejected", rule, tally) do
    gap = gap(tally)

    cond do
      Decimal.lt?(gap, 0) and not Decimal.lt?(Decimal.negate(gap), required(rule, tally)) ->
        :fell_past_rule

      Decimal.gt?(gap, 0) ->
        :rose_short_of_rule

      Decimal.eq?(gap, 0) ->
        :unchanged

      true ->
        :fell_short_of_rule
    end
  end

  defp inconsistent(sentence, details),
    do: {:error, Error.new(:submission_result_inconsistent, sentence, details)}

  # -- The Skill change ------------------------------------------------------

  defp change(
         %{"pointer" => pointer, "baseline" => baseline, "candidate" => candidate} = difference,
         prefix,
         maximum,
         candidate_skills
       )
       when map_size(difference) == 3 and is_binary(pointer) do
    with ["", place] <- String.split(pointer, prefix, parts: 2),
         {:ok, skill, field} <- place(place, maximum),
         {:ok, without} <- value(field, baseline),
         {:ok, with_skill} <- value(field, candidate) do
      change = %{skill: skill, field: field, without: without, with: with_skill}

      if fingerprint_agrees?(change, candidate_skills),
        do: {:ok, change},
        else: fingerprint_mismatch(pointer)
    else
      _other -> invalid_change(pointer)
    end
  end

  defp change(difference, _prefix, _maximum, _candidate_skills),
    do: invalid_change(pointer(difference))

  defp pointer(%{"pointer" => pointer}) when is_binary(pointer), do: pointer
  defp pointer(_difference), do: nil

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

  defp value(nil, nil), do: {:ok, %{kind: :none}}

  defp value(nil, %{"digest" => digest, "media_type" => media_type, "size" => size} = reference) do
    if Enum.all?(Map.keys(reference), &(&1 in @skill_reference_keys)) and Digest.valid?(digest) and
         text?(media_type) and positive?(size) and optional_text?(reference["relative_path"]),
       do: {:ok, %{kind: :skill, digest: digest, size: size}},
       else: :error
  end

  defp value("digest", digest) when is_binary(digest),
    do: if(Digest.valid?(digest), do: {:ok, %{kind: :digest, digest: digest}}, else: :error)

  defp value("size", size),
    do: if(positive?(size), do: {:ok, %{kind: :size, size: size}}, else: :error)

  defp value("media_type", text),
    do: if(text?(text), do: {:ok, %{kind: :text, text: text}}, else: :error)

  defp value("relative_path", nil), do: {:ok, %{kind: :not_set}}

  defp value("relative_path", text),
    do: if(text?(text), do: {:ok, %{kind: :text, text: text}}, else: :error)

  defp value(_field, _value), do: :error

  defp text?(value), do: is_binary(value) and value != ""
  defp optional_text?(value), do: is_nil(value) or text?(value)
  defp positive?(value), do: is_integer(value) and value > 0

  # A fingerprint the comparison gives the candidate's Skill is the one the
  # candidate run's own settings give the Skill at that place.
  defp fingerprint_agrees?(%{skill: skill, with: %{digest: digest}}, candidate_skills),
    do: match?(%{"digest" => ^digest}, Enum.at(candidate_skills, skill))

  defp fingerprint_agrees?(_change, _candidate_skills), do: true

  defp invalid_change(pointer) do
    {:error,
     Error.new(
       :submission_skill_change_invalid,
       "a difference this result names between its two runs is not a Skill its Campaign " <>
         "lets differ, written the way the CLI writes one",
       %{"pointer" => pointer}
     )}
  end

  defp fingerprint_mismatch(pointer) do
    {:error,
     Error.new(
       :submission_skill_change_invalid,
       "the Skill fingerprint this result's comparison names is not the one the run with " <>
         "the Skill was set up with",
       %{"pointer" => pointer}
     )}
  end
end
