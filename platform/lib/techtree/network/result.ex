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

  A model change (`model_substitution`, `docs/spec/model-substitution-v1.md`)
  is read more strictly, because both runs' settings are compared here rather
  than taken from the report. The two runs may differ only in the model's
  weights, plus the candidate's derivation record, which must point at the
  candidate's own weights and at the baseline's model as their source. The
  baseline must be the model the Campaign names, the weights must really
  differ, and the report's list of differences must be exactly the one this
  site works out itself, so a difference the report leaves out is caught.
  """

  alias Techtree.Catalog.Digest
  alias Techtree.Network.Error

  @decisions ~w(accepted rejected inconclusive)
  @controlled ~w(controlled controlled_with_warnings)

  @skill_fields ~w(digest media_type size relative_path)
  @skill_reference_keys ~w(digest media_type relative_path size)

  @weights_pointer "/agents/subject/model/weights"
  @derivation_pointer "/agents/subject/model/derivation"
  @model_keys ~w(chat_template_digest derivation serving tokenizer_digest weights)
  @weights_keys ~w(repo revision weights_root)
  @serving_keys ~w(dtype engine max_model_len quantization version)
  @derivation_keys ~w(method method_config_digest seed source tool tool_commit weights_root)
  @source_keys ~w(repo revision)
  @commit ~r/\A[0-9a-f]{40}\z/

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

  @typedoc "One run's open weights: where they came from and their root digest."
  @type weights :: %{
          repo: String.t() | nil,
          revision: String.t() | nil,
          weights_root: String.t()
        }

  @typedoc """
  The model change a report measured: the two runs' weights, and the record of
  how the candidate's were made from the baseline's, when it carries one.
  """
  @type model_change :: %{baseline: weights(), candidate: weights(), derivation: map() | nil}

  @doc """
  Recompute a report's result under its Campaign, or name what does not hold.
  """
  @spec assess(map(), map()) :: {:ok, t()} | {:error, Error.t()}
  def assess(report, campaign) when is_map(report) and is_map(campaign) do
    Decimal.Context.with(@exact, fn ->
      with {:ok, rows} <- rows(report["task_deltas"]),
           {:ok, written} <- written(report["primary_result"]),
           :ok <- reportable(report),
           {:ok, decision} <- decision(report["decision"]),
           :ok <- model_build_agrees(report["statuses"]),
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

  @doc """
  What changed between the two runs of a `model_substitution` Campaign: only
  the model's weights, and the candidate's record of how they were made.

  `baseline` and `candidate` are the `configuration` of the two runs'
  experiment manifests, read from the bundle. Both are compared here, leaf by
  leaf, the same way the CLI compares them, and the report's own list of
  differences must be exactly that comparison.
  """
  @spec model_change(map(), map(), map(), map()) :: {:ok, model_change()} | {:error, Error.t()}
  def model_change(report, campaign, baseline, candidate)
      when is_map(report) and is_map(campaign) and is_map(baseline) and is_map(candidate) do
    with :ok <- model_contract(campaign),
         {:ok, reported} <- reported_differences(report),
         {:ok, before} <- open_weights(baseline, "the run without the change"),
         {:ok, now} <- open_weights(candidate, "the run with the change"),
         :ok <- named_by_campaign(before, campaign),
         differences = baseline |> differences(candidate, "") |> Enum.sort_by(& &1["pointer"]),
         :ok <- only_the_weights(differences),
         :ok <- weights_differ(before, now),
         :ok <- derived_from(before, now),
         :ok <- reported_as_found(reported, differences) do
      {:ok,
       %{
         baseline: weights(before["weights"]),
         candidate: weights(now["weights"]),
         derivation: now["derivation"]
       }}
    end
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

  defp written(%{"wins" => wins, "losses" => losses, "ties" => ties})
       when is_integer(wins) and is_integer(losses) and is_integer(ties),
       do: {:ok, %{wins: wins, losses: losses, ties: ties}}

  defp written(_result) do
    inconsistent("this result does not state its counts of better, worse and same tasks", %{})
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

  # A Campaign names a model, never a build of it, so the two runs are known
  # to share a model name only, and the report's comparison must say so.
  defp model_build_agrees(%{"comparison" => "controlled_with_warnings"}), do: :ok

  defp model_build_agrees(statuses) do
    inconsistent(
      "a Campaign names no model build, so this result's comparison must warn that its " <>
        "runs share a model name only, and this one does not",
      %{"comparison" => statuses["comparison"]}
    )
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

  # -- The model change ------------------------------------------------------

  defp model_contract(%{
         "mutation_contract" => %{
           "kind" => "model_substitution",
           "target_agent" => "subject",
           "allowed_differences" => [@weights_pointer]
         }
       }),
       do: :ok

  defp model_contract(campaign) do
    model_change_invalid(
      "this result's Campaign does not let only the model's weights differ",
      %{"mutation_contract" => campaign["mutation_contract"]}
    )
  end

  defp reported_differences(%{
         "manifest_comparison" => %{
           "controlled" => true,
           "violations" => [],
           "allowed_differences" => [@weights_pointer],
           "differences" => [_ | _] = differences
         }
       }),
       do: {:ok, differences}

  defp reported_differences(_report) do
    model_change_invalid(
      "this result's report does not show its two runs as differing only in the model's weights",
      %{}
    )
  end

  defp open_weights(configuration, side) do
    model = fetch_in(configuration, ["agents", "subject", "model"])

    if open_weights?(model) do
      {:ok, model}
    else
      model_change_invalid(
        side <>
          " does not name its model as open weights, written the way the contract writes them",
        %{"pointer" => "/agents/subject/model"}
      )
    end
  end

  defp open_weights?(model) do
    keys?(model, @model_keys) and weights?(model["weights"]) and
      Digest.valid?(model["tokenizer_digest"]) and Digest.valid?(model["chat_template_digest"]) and
      serving?(model["serving"]) and
      (is_nil(model["derivation"]) or derivation?(model["derivation"]))
  end

  # A revision is a commit of the repository it names, so it never comes alone.
  defp weights?(weights) do
    keys?(weights, @weights_keys) and optional_text?(weights["repo"]) and
      (is_nil(weights["revision"]) or (commit?(weights["revision"]) and text?(weights["repo"]))) and
      Digest.valid?(weights["weights_root"])
  end

  defp serving?(serving) do
    keys?(serving, @serving_keys) and serving["engine"] == "vllm" and text?(serving["version"]) and
      text?(serving["dtype"]) and optional_text?(serving["quantization"]) and
      positive?(serving["max_model_len"])
  end

  defp derivation?(derivation) do
    keys?(derivation, @derivation_keys) and text?(derivation["tool"]) and
      commit?(derivation["tool_commit"]) and source?(derivation["source"]) and
      text?(derivation["method"]) and Digest.valid?(derivation["method_config_digest"]) and
      (is_nil(derivation["seed"]) or is_integer(derivation["seed"])) and
      Digest.valid?(derivation["weights_root"])
  end

  defp source?(source),
    do: keys?(source, @source_keys) and text?(source["repo"]) and commit?(source["revision"])

  defp keys?(map, keys), do: is_map(map) and Enum.sort(Map.keys(map)) == keys
  defp commit?(value), do: is_binary(value) and Regex.match?(@commit, value)

  # The Campaign describes the run without the change, and names its model
  # exactly: by repository and commit.
  defp named_by_campaign(%{"weights" => weights} = model, campaign) do
    if model == fetch_in(campaign, ["agents", "subject", "model"]) and text?(weights["repo"]) and
         commit?(weights["revision"]) do
      :ok
    else
      model_change_invalid(
        "the run without the change is not the model its Campaign names, by repository and commit",
        %{"pointer" => "/agents/subject/model"}
      )
    end
  end

  # Every leaf at which the two settings disagree, as an RFC 6901 pointer, the
  # way the CLI's `diff_values` finds them: descend only where both sides are
  # the same kind of container, and report anything else whole.
  defp differences(%{} = baseline, %{} = candidate, pointer) do
    (Map.keys(baseline) ++ Map.keys(candidate))
    |> Enum.uniq()
    |> Enum.sort()
    |> Enum.flat_map(fn key ->
      child = pointer <> "/" <> escape(key)
      pair(Map.fetch(baseline, key), Map.fetch(candidate, key), child)
    end)
  end

  defp differences(baseline, candidate, pointer) when is_list(baseline) and is_list(candidate) do
    0
    |> Range.new(max(length(baseline), length(candidate)) - 1, 1)
    |> Enum.flat_map(fn index ->
      child = pointer <> "/" <> Integer.to_string(index)
      pair(Enum.fetch(baseline, index), Enum.fetch(candidate, index), child)
    end)
  end

  defp differences(baseline, candidate, pointer) do
    if same_scalar?(baseline, candidate),
      do: [],
      else: [difference(pointer, baseline, candidate)]
  end

  defp pair(:error, {:ok, value}, pointer), do: [difference(pointer, nil, value)]
  defp pair({:ok, value}, :error, pointer), do: [difference(pointer, value, nil)]
  defp pair({:ok, left}, {:ok, right}, pointer), do: differences(left, right, pointer)

  # JSON has one kind of number, so 1 and 1.0 are the same value; a boolean is
  # never a number.
  defp same_scalar?(left, right) when is_number(left) and is_number(right), do: left == right
  defp same_scalar?(left, right), do: left === right

  defp difference(pointer, baseline, candidate),
    do: %{"pointer" => pointer, "baseline" => baseline, "candidate" => candidate}

  defp escape(key), do: key |> String.replace("~", "~0") |> String.replace("/", "~1")

  defp only_the_weights(differences) do
    case Enum.find(differences, &(not model_pointer?(&1["pointer"]))) do
      nil ->
        :ok

      %{"pointer" => pointer} ->
        model_change_invalid(
          "the two runs differ in a setting other than the model's weights",
          %{"pointer" => pointer}
        )
    end
  end

  defp model_pointer?(pointer),
    do:
      pointer in [@weights_pointer, @derivation_pointer] or
        String.starts_with?(pointer, @weights_pointer <> "/")

  defp weights_differ(%{"weights" => %{"weights_root" => root}}, %{
         "weights" => %{"weights_root" => root}
       }) do
    model_change_invalid(
      "both runs name the same weights, so the comparison measures no change",
      %{"pointer" => @weights_pointer <> "/weights_root"}
    )
  end

  defp weights_differ(_baseline, _candidate), do: :ok

  # The baseline is the source model, so only the candidate's weights carry a
  # record of how they were made, and that record names those weights and the
  # baseline's model.
  defp derived_from(%{"derivation" => nil, "weights" => source}, %{
         "derivation" => derivation,
         "weights" => weights
       }) do
    if is_nil(derivation) or
         (derivation["weights_root"] == weights["weights_root"] and
            derivation["source"] == Map.take(source, @source_keys)) do
      :ok
    else
      model_change_invalid(
        "the candidate's derivation record does not name its own weights and the baseline's " <>
          "model as their source",
        %{"pointer" => @derivation_pointer}
      )
    end
  end

  defp derived_from(_baseline, _candidate) do
    model_change_invalid(
      "the run without the change carries a derivation record, and only the changed weights " <>
        "are derived",
      %{"pointer" => @derivation_pointer}
    )
  end

  defp reported_as_found(reported, differences) do
    if Enum.sort_by(reported, &pointer/1) == differences do
      :ok
    else
      model_change_invalid(
        "the differences this result's report lists are not the ones its two runs' settings give",
        %{
          "reported" => Enum.map(reported, &pointer/1),
          "recomputed" => Enum.map(differences, & &1["pointer"])
        }
      )
    end
  end

  defp weights(weights) do
    %{
      repo: weights["repo"],
      revision: weights["revision"],
      weights_root: weights["weights_root"]
    }
  end

  defp fetch_in(value, []), do: value
  defp fetch_in(%{} = map, [key | path]), do: fetch_in(Map.get(map, key), path)
  defp fetch_in(_value, _path), do: nil

  defp model_change_invalid(sentence, details),
    do: {:error, Error.new(:submission_model_change_invalid, sentence, details)}
end
