defmodule Techtree.Network.ResultTest do
  @moduledoc """
  The verdict a published Result is shown under, worked out from its own task
  scores and its Campaign's rule.

  Each test takes the fixture's signed report and its Campaign and changes the
  one thing the verdict turns on, writing the rest of the report the way the
  CLI would write it for that change. The ingest tests show a report that is
  wrong about itself being refused; these show what an honest one reads as.
  """

  use ExUnit.Case, async: true

  alias Techtree.Network.Result
  alias Techtree.NetworkFixture

  @campaign "test/support/fixtures/proof-v2/campaign.json" |> File.read!() |> Jason.decode!()

  test "a rejected report with no change at all is not enough evidence, even written as -0.0" do
    for written <- [0.0, -0.0] do
      report =
        report()
        |> Map.update!("task_deltas", fn deltas ->
          Enum.map(deltas, &%{&1 | "candidate_reward" => &1["baseline_reward"], "delta" => 0})
        end)
        |> Map.update!(
          "primary_result",
          &Map.merge(&1, %{
            "candidate_mean" => &1["baseline_mean"],
            "absolute_delta" => written,
            "relative_delta" => 0.0,
            "wins" => 0,
            "losses" => 0,
            "ties" => 36
          })
        )
        |> Map.put("decision", "rejected")

      assert {:ok, result} = Result.assess(report, @campaign)
      assert result.verdict == :not_enough_evidence
      assert result.why == {:short_of_rule, :same}
      assert Decimal.eq?(result.absolute_delta, 0)
    end
  end

  test "a lower score is a regression only when it falls by the Campaign's minimum" do
    swapped = swapped_sides(report())

    assert {:ok, %Result{verdict: :regressed, why: :worse_past_rule}} =
             Result.assess(swapped, @campaign)

    # The Skill scored 22.2 points lower, short of a 30-point minimum.
    campaign = put_in(@campaign, ["scoring", "minimum_absolute_delta"], 0.3)

    assert {:ok, %Result{verdict: :not_enough_evidence, why: {:short_of_rule, :lower}}} =
             Result.assess(swapped, campaign)
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

    assert {:ok, %Result{verdict: :not_enough_evidence, why: :no_rule}} =
             Result.assess(report, campaign)
  end

  test "a development-only report says why it makes no call, from its own statuses" do
    development = fn statuses ->
      report()
      |> Map.merge(%{"proof_grade" => "development_only", "decision" => "development_only"})
      |> Map.update!("statuses", &Map.merge(&1, statuses))
    end

    assert {:ok, %Result{verdict: :not_enough_evidence, why: {:score_not_valid, "errored"}}} =
             Result.assess(development.(%{"score" => "errored"}), @campaign)

    assert {:ok, %Result{why: :not_controlled}} =
             Result.assess(development.(%{"comparison" => "invalid"}), @campaign)

    assert {:ok, %Result{why: :not_sealed}} = Result.assess(development.(%{}), @campaign)
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
      %{
        result
        | "baseline_mean" => result["candidate_mean"],
          "candidate_mean" => result["baseline_mean"],
          "absolute_delta" => -result["absolute_delta"],
          "wins" => result["losses"],
          "losses" => result["wins"]
      }
    end)
    |> Map.put("decision", "rejected")
  end
end
