defmodule Techtree.Network.ResultTest do
  @moduledoc """
  The verdict a published Result is shown under, worked out from its own task
  scores and its Campaign's rule, and the reports the CLI would never publish.

  Each test takes the fixture's signed report and its Campaign and changes the
  one thing it is about, writing the rest of the report the way the CLI would
  write it for that change.
  """

  use ExUnit.Case, async: true

  alias Techtree.Network.Result
  alias Techtree.NetworkFixture

  @campaign "test/support/fixtures/proof-v2/campaign.json" |> File.read!() |> Jason.decode!()

  test "a rejected report with no change at all is not enough evidence, never a regression" do
    report =
      report()
      |> Map.update!("task_deltas", fn deltas ->
        Enum.map(deltas, &%{&1 | "candidate_reward" => &1["baseline_reward"], "delta" => 0})
      end)
      |> Map.update!(
        "primary_result",
        &Map.merge(&1, %{"wins" => 0, "losses" => 0, "ties" => 36})
      )
      |> Map.put("decision", "rejected")

    assert {:ok, result} = Result.assess(report, @campaign)
    assert result.reason == :unchanged
    assert Decimal.eq?(result.candidate_total, result.baseline_total)
  end

  test "a lower score is a regression only when it falls by the Campaign's minimum" do
    swapped = swapped_sides(report())

    assert {:ok, %{reason: :fell_past_rule}} = Result.assess(swapped, @campaign)

    # The Skill scored 22.2 points lower, short of a 30-point minimum.
    campaign = put_in(@campaign, ["scoring", "minimum_absolute_delta"], 0.3)

    assert {:ok, %{reason: :fell_short_of_rule}} = Result.assess(swapped, campaign)
  end

  test "an improvement exactly at the Campaign's minimum is accepted" do
    # Ten tasks, one more solved with the Skill: a rise of exactly 0.1, which
    # binary floating point puts below 0.1 (0.6 - 0.5). Both this site and the
    # CLI read the scores as the decimals the report carries, and accept it.
    deltas =
      for task <- 0..9 do
        baseline = if task < 5, do: 1.0, else: 0.0
        candidate = if task < 6, do: 1.0, else: 0.0

        %{
          "task_hash" => "sha256:" <> String.duplicate(Integer.to_string(task), 64),
          "baseline_reward" => baseline,
          "candidate_reward" => candidate,
          "delta" => candidate - baseline
        }
      end

    report =
      report()
      |> Map.put("task_deltas", deltas)
      |> Map.update!("primary_result", &Map.merge(&1, %{"wins" => 1, "losses" => 0, "ties" => 9}))
      |> Map.put("decision", "accepted")

    campaign = put_in(@campaign, ["scoring", "minimum_absolute_delta"], 0.1)

    assert {:ok, result} = Result.assess(report, campaign)
    assert result.reason == :cleared_rule
    assert Decimal.eq?(result.baseline_total, 5)
    assert Decimal.eq?(result.candidate_total, 6)
    assert result.task_count == 10
  end

  test "a Campaign with no rule to decide by gives an inconclusive report" do
    campaign =
      update_in(
        @campaign,
        ["scoring"],
        &Map.merge(&1, %{
          "require_candidate_above_baseline" => false,
          "minimum_absolute_delta" => 0
        })
      )

    report = Map.put(report(), "decision", "inconclusive")

    assert {:ok, %{reason: :no_rule}} = Result.assess(report, campaign)
  end

  test "a decision the CLI never writes is refused" do
    for decision <- ["maybe", "development_only", "invalid"] do
      assert {:error, %{code: :submission_result_inconsistent}} =
               Result.assess(Map.put(report(), "decision", decision), @campaign)
    end
  end

  test "a report the CLI would not publish is refused, whatever it is graded" do
    for changes <- [
          %{"statuses" => %{"score" => "invalid"}},
          %{"statuses" => %{"score" => "errored"}},
          %{"statuses" => %{"comparison" => "invalid"}},
          %{"proof_grade" => "development_only"}
        ] do
      report =
        report()
        |> Map.update!("statuses", &Map.merge(&1, Map.get(changes, "statuses", %{})))
        |> Map.merge(Map.delete(changes, "statuses"))

      assert {:error, %{code: :submission_result_inconsistent}} = Result.assess(report, @campaign)
    end
  end

  test "a comparison that claims a model build its Campaign never named is refused" do
    report = put_in(report(), ["statuses", "comparison"], "controlled")

    assert {:error, %{code: :submission_result_inconsistent, details: details}} =
             Result.assess(report, @campaign)

    assert details == %{"comparison" => "controlled"}
  end

  test "the Skill fingerprint must be the one the run with the Skill was set up with" do
    [%{"candidate" => candidate}] = report()["manifest_comparison"]["differences"]

    assert {:ok, [%{with: %{kind: :skill, digest: digest}}]} =
             Result.skill_change(report(), @campaign, [candidate])

    assert digest == candidate["digest"]

    other = %{candidate | "digest" => "sha256:" <> String.duplicate("a", 64)}

    assert {:error, %{code: :submission_skill_change_invalid}} =
             Result.skill_change(report(), @campaign, [other])
  end

  defp report, do: NetworkFixture.report()["payload"]

  defp swapped_sides(report) do
    report
    |> Map.update!("task_deltas", fn deltas ->
      Enum.map(deltas, fn delta ->
        %{
          delta
          | "baseline_reward" => delta["candidate_reward"],
            "candidate_reward" => delta["baseline_reward"],
            "delta" => -delta["delta"]
        }
      end)
    end)
    |> Map.update!("primary_result", fn result ->
      %{result | "wins" => result["losses"], "losses" => result["wins"]}
    end)
    |> Map.put("decision", "rejected")
  end
end
