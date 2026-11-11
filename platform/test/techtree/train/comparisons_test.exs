defmodule Techtree.Train.ComparisonsTest do
  @moduledoc """
  The Train reports as the pages read them: a report shows only when its own
  digest and its traces' digest check out, every report in the folder is
  read, newest first, and the arm names and changes are the report's own.
  The reports are written by `Techtree.TrainFixture` into a folder of each
  test's own, except the last two tests, which read the committed folders.
  """

  use ExUnit.Case, async: true

  import ExUnit.CaptureLog

  alias Techtree.Canonical
  alias Techtree.Catalog.Digest
  alias Techtree.Train.Comparisons
  alias Techtree.TrainFixture

  describe "one folder" do
    @describetag :tmp_dir

    test "a Skill report is read with its figures counted from its tasks", %{tmp_dir: folder} do
      TrainFixture.write!(folder, "nano-skill", results: {30, 28, 6})

      assert [comparison] = Comparisons.list(folder)

      assert %{
               slug: "nano-skill",
               change: :skill,
               outcome: :uplift,
               paired: %{wins: 30, ties: 28, losses: 6},
               environment: %{split: "held_out", task_count: 64}
             } = comparison

      assert [
               %{name: "baseline", change: :none, skill_digest: nil, adapter: nil},
               %{name: "skill", change: :skill, skill_digest: "sha256:" <> _, adapter: nil}
             ] = comparison.arms

      assert length(comparison.tasks) == 64
      assert Enum.count(comparison.tasks, &(&1.result == :win)) == 30
      assert {:ok, ^comparison} = Comparisons.fetch("nano-skill", folder)
    end

    test "an RL report keeps its own arm names and change", %{tmp_dir: folder} do
      TrainFixture.write!(folder, "lightning-rl", change: :rl)

      assert {:ok, comparison} = Comparisons.fetch("lightning-rl", folder)
      assert comparison.change == :rl

      assert [
               %{name: "baseline", change: :none, adapter: nil},
               %{
                 name: "trained",
                 change: :rl,
                 skill_digest: nil,
                 adapter: "techtree/payment-terms-lora-step-50"
               }
             ] = comparison.arms
    end

    test "every report is listed, newest first, then by slug", %{tmp_dir: folder} do
      TrainFixture.write!(folder, "older", finished_at: "2026-11-09T12:00:00Z")
      TrainFixture.write!(folder, "newest", change: :rl, finished_at: "2026-11-11T08:00:00Z")
      TrainFixture.write!(folder, "same-time-b", finished_at: "2026-11-10T10:00:00Z")
      TrainFixture.write!(folder, "same-time-a", finished_at: "2026-11-10T10:00:00Z")

      assert Enum.map(Comparisons.list(folder), & &1.slug) ==
               ["newest", "same-time-a", "same-time-b", "older"]
    end

    test "a folder with no reports, or no folder at all, lists none", %{tmp_dir: folder} do
      assert Comparisons.list(folder) == []
      assert Comparisons.list(Path.join(folder, "not-there")) == []
    end

    test "a report whose spec no longer matches its digest is refused", %{tmp_dir: folder} do
      TrainFixture.write!(folder, "shown")
      TrainFixture.write!(folder, "changed")
      edit_report!(folder, "changed", &put_in(&1, ["spec", "title"], "A better score"))

      assert [{"changed", {:error, :digest}}, {"shown", {:ok, _}}] = Comparisons.read_all(folder)
      assert refused(folder, "changed") =~ "Train comparison changed refused: digest mismatch"
    end

    test "a report whose traces are not the ones it names is refused", %{tmp_dir: folder} do
      TrainFixture.write!(folder, "shown")
      TrainFixture.write!(folder, "other-traces")
      File.write!(Path.join(folder, "other-traces.traces.jsonl"), "{}\n", [:append])

      assert [{"other-traces", {:error, :traces}}, {"shown", {:ok, _}}] =
               Comparisons.read_all(folder)

      assert refused(folder, "other-traces") =~ "Train comparison other-traces refused: traces mismatch"
    end

    test "counts a report gives that its tasks do not bear out are not read", %{tmp_dir: folder} do
      TrainFixture.write!(folder, "miscounted")
      rewrite_report!(folder, "miscounted", &put_in(&1, ["spec", "results", "paired", "wins"], 31))

      assert_raise MatchError, fn -> Comparisons.list(folder) end
    end

    test "a download is the file's exact bytes and their digest", %{tmp_dir: folder} do
      TrainFixture.write!(folder, "nano-skill")
      report = File.read!(Path.join(folder, "nano-skill.json"))
      traces = File.read!(Path.join(folder, "nano-skill.traces.jsonl"))

      assert Comparisons.download("nano-skill", :report, folder) ==
               {:ok, report, Digest.hash_bytes(report)}

      assert Comparisons.download("nano-skill", :traces, folder) ==
               {:ok, traces, Digest.hash_bytes(traces)}
    end

    test "a name the folder has no report for is not found", %{tmp_dir: folder} do
      TrainFixture.write!(folder, "nano-skill")

      for slug <- ["missing", "../nano-skill", "nano-skill.json", "NANO-SKILL"] do
        assert Comparisons.fetch(slug, folder) == :error
        assert Comparisons.download(slug, :report, folder) == :error
      end
    end
  end

  test "the test folder's reports both check out" do
    assert [{"nemotron-lightning-rl", {:ok, %{change: :rl}}}, {"nemotron-nano-skill", {:ok, %{change: :skill}}}] =
             Comparisons.read_all(Comparisons.folder())
  end

  test "every report committed for the release checks out" do
    for {slug, read} <- Comparisons.read_all(Application.app_dir(:techtree, ["priv", "train"])) do
      assert {:ok, _comparison} = read, "#{slug} is refused: #{inspect(read)}"
    end
  end

  # Change a written report and leave its digest as it was.
  defp edit_report!(folder, slug, change) do
    path = Path.join(folder, slug <> ".json")
    File.write!(path, path |> File.read!() |> Jason.decode!() |> change.() |> Jason.encode!())
  end

  # Change a written report and work its digest out again, as the runner would
  # have written the changed report.
  defp rewrite_report!(folder, slug, change) do
    edit_report!(folder, slug, fn report ->
      report = change.(report)
      named = Map.take(report, ["schema_version", "kind", "spec"])
      Map.put(report, "digest", named |> Canonical.encode!() |> Digest.hash_bytes())
    end)
  end

  defp refused(folder, slug) do
    capture_log(fn ->
      assert Comparisons.list(folder) |> Enum.map(& &1.slug) == ["shown"]
      assert Comparisons.fetch(slug, folder) == :error
      assert Comparisons.download(slug, :report, folder) == :error
    end)
  end
end
