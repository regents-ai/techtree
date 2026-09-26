defmodule TechtreeWeb.TddShowcaseTest do
  @moduledoc """
  The showcase loader against the test folders the CLI's scripted stand-ins
  wrote: what it works out from the scores, and that it refuses files that
  disagree with each other or lack a field the page draws.

  The variants are comparisons of further stand-in runs on the same tasks,
  each put in place of the folder's own comparison.
  """

  use ExUnit.Case, async: true

  alias TechtreeWeb.TddShowcase

  @fixture Path.expand("../support/fixtures/tdd-showcase", __DIR__)
  @variants Path.expand("../support/fixtures/tdd-showcase-variants", __DIR__)

  setup_all do
    %{showcase: TddShowcase.load!(@fixture)}
  end

  test "the configured folder is the test folder" do
    assert TddShowcase.folder() == @fixture
  end

  test "the verdict and its tasks come from the held-out part alone", %{showcase: showcase} do
    assert %{verdict: :mixed, wins: 2, losses: 1, ties: 1, unresolved: 0, graded: 4} =
             showcase.held_out

    assert names(showcase.held_out) == %{
             better: ["tdd-date-ranges", "tdd-cache-rewrite"],
             worse: ["tdd-parser-kept"],
             same: ["tdd-slugify"],
             not_scored: []
           }

    assert Enum.all?(showcase.held_out.tasks, &(&1.part == :held_out))
  end

  test "the study part is kept apart with its own verdict", %{showcase: showcase} do
    assert %{verdict: :improved, wins: 2, losses: 0, ties: 2} = showcase.study
    assert Enum.all?(showcase.study.tasks, &(&1.part == :study))

    assert names(showcase.study) == %{
             better: ["tdd-cart-total", "tdd-roman-numerals"],
             worse: [],
             same: ["tdd-rate-limiter", "tdd-csv-report"],
             not_scored: []
           }
  end

  test "each claim carries the tasks that test it, and every task sits under one claim",
       %{showcase: showcase} do
    assert Enum.map(showcase.claims, & &1.id) == ["C1", "C2", "C3"]

    assert showcase.claims |> Enum.flat_map(& &1.tasks) |> Enum.map(& &1.id) |> Enum.sort() ==
             showcase.tasks |> Enum.map(& &1.id) |> Enum.sort()

    assert Enum.all?(showcase.claims, fn claim ->
             Enum.all?(claim.tasks, &(&1.claim == claim.id))
           end)
  end

  test "the Skill, the runs' settings and the commands come from the committed files",
       %{showcase: showcase} do
    assert %{name: "tdd", digest: "sha256:" <> _} = showcase.skill

    assert Enum.map(showcase.skill.files, & &1.path) ==
             ["LICENSE.txt", "SKILL.md", "agents/openai.yaml", "mocking.md", "tests.md"]

    assert showcase.skill.licence == %{
             name: "MIT License",
             copyright: "Copyright (c) 2026 Matt Pocock"
           }

    assert showcase.model == %{
             provider: "openai-codex",
             model_id: "gpt-5.6-sol",
             reasoning: "medium"
           }

    assert showcase.limits == %{cpus: 2, memory_mb: 4096}
    assert showcase.not_established == [:served_model, :agent_unmodified, :sampling]
    assert "sha256:" <> _ = showcase.fingerprint
    assert length(showcase.commands) == 6
    assert Enum.all?(showcase.tasks, &(&1.time_limit == "30 minutes"))
  end

  describe "the verdict worked out from the scores" do
    @describetag :tmp_dir

    test "held-out tasks that only got worse or stayed the same regressed", %{tmp_dir: tmp_dir} do
      held_out = variant(tmp_dir, "regressed").held_out

      assert %{verdict: :regressed, wins: 0, losses: 2, ties: 2} = held_out
      assert names(held_out).worse == ["tdd-date-ranges", "tdd-cache-rewrite"]
    end

    test "held-out tasks that all stayed the same made no difference", %{tmp_dir: tmp_dir} do
      held_out = variant(tmp_dir, "no-difference").held_out

      assert %{verdict: :no_difference, ties: 4, baseline_mean: 1.0, candidate_mean: 1.0} =
               held_out
    end

    test "one held-out task missing a score leaves no verdict, and says why", %{tmp_dir: tmp_dir} do
      held_out = variant(tmp_dir, "one-failed").held_out

      assert %{verdict: :inconclusive, graded: 3, unresolved: 1} = held_out

      assert [%{name: "tdd-parser-kept", unscored: [%{run: :candidate, ended: :no_verdict}]}] =
               TddShowcase.by_outcome(held_out.tasks).not_scored
    end

    test "fewer held-out tasks scored on both runs than a verdict needs leaves none",
         %{tmp_dir: tmp_dir} do
      held_out = variant(tmp_dir, "too-few").held_out

      assert %{verdict: :inconclusive, graded: 2, unresolved: 2} = held_out
      assert held_out.graded < TddShowcase.verdict_minimum_pairs()

      assert [
               %{
                 name: "tdd-cache-rewrite",
                 unscored: [%{run: :baseline, ended: :verifier_timed_out}]
               },
               %{name: "tdd-slugify", unscored: [%{run: :candidate, ended: :no_verdict}]}
             ] = TddShowcase.by_outcome(held_out.tasks).not_scored

      assert {held_out.baseline_mean, held_out.candidate_mean} == {0.5, 1.0}
    end
  end

  describe "files that disagree or lack a field" do
    @describetag :tmp_dir

    test "a stored verdict that the scores do not give is refused", %{tmp_dir: tmp_dir} do
      folder = copy_fixture(tmp_dir)
      edit_json(folder, "comparison.json", &put_in(&1, ["held_out", "verdict"], "improved"))

      assert_raise MatchError, fn -> TddShowcase.load!(folder) end
    end

    test "a study task moved into the held-out part is refused", %{tmp_dir: tmp_dir} do
      folder = copy_fixture(tmp_dir)

      edit_json(folder, "comparison.json", fn comparison ->
        [moved | study] = comparison["study"]["task_ids"]

        comparison
        |> put_in(["study", "task_ids"], study)
        |> update_in(["held_out", "task_ids"], &(&1 ++ [moved]))
      end)

      assert_raise MatchError, fn -> TddShowcase.load!(folder) end
    end

    test "a Skill file changed after the run is refused", %{tmp_dir: tmp_dir} do
      folder = copy_fixture(tmp_dir)
      File.write!(Path.join([folder, "skill", "tdd", "SKILL.md"]), "changed\n", [:append])

      assert_raise MatchError, fn -> TddShowcase.load!(folder) end
    end

    test "an extra file beside the Skill's recorded files is refused", %{tmp_dir: tmp_dir} do
      folder = copy_fixture(tmp_dir)
      File.write!(Path.join([folder, "skill", "tdd", "extra.md"]), "extra\n")

      assert_raise MatchError, fn -> TddShowcase.load!(folder) end
    end

    test "a run specification that is not the one the comparison names is refused",
         %{tmp_dir: tmp_dir} do
      folder = copy_fixture(tmp_dir)

      edit_json(
        folder,
        "runs/baseline/spec.json",
        &put_in(&1, ["limits", "container_memory_mb"], 8192)
      )

      assert_raise MatchError, fn -> TddShowcase.load!(folder) end
    end

    test "an export README that is not the one its record names is refused", %{tmp_dir: tmp_dir} do
      folder = copy_fixture(tmp_dir)
      File.write!(Path.join([folder, "export", "README.md"]), "\n", [:append])

      assert_raise MatchError, fn -> TddShowcase.load!(folder) end
    end

    test "an export of different tasks is refused", %{tmp_dir: tmp_dir} do
      folder = copy_fixture(tmp_dir)

      edit_json(
        folder,
        "export/export.json",
        &put_in(&1, ["collection", "collection_digest"], "sha256:" <> String.duplicate("0", 64))
      )

      assert_raise MatchError, fn -> TddShowcase.load!(folder) end
    end

    test "a missing field the page draws is refused", %{tmp_dir: tmp_dir} do
      folder = copy_fixture(tmp_dir)
      edit_json(folder, "comparison.json", &Map.delete(&1, "not_established"))

      assert_raise MatchError, fn -> TddShowcase.load!(folder) end
    end
  end

  defp names(part) do
    part.tasks
    |> TddShowcase.by_outcome()
    |> Map.new(fn {outcome, tasks} -> {outcome, Enum.map(tasks, & &1.name)} end)
  end

  defp variant(tmp_dir, name) do
    folder = copy_fixture(tmp_dir)

    File.cp!(
      Path.join([@variants, name, "comparison.json"]),
      Path.join(folder, "comparison.json")
    )

    TddShowcase.load!(folder)
  end

  defp copy_fixture(tmp_dir) do
    folder = Path.join(tmp_dir, "tdd-showcase")
    File.cp_r!(@fixture, folder)
    folder
  end

  defp edit_json(folder, relative, change) do
    path = Path.join(folder, relative)

    path
    |> File.read!()
    |> Jason.decode!()
    |> change.()
    |> Jason.encode!()
    |> then(&File.write!(path, &1))
  end
end
