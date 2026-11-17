defmodule Techtree.Train.ComparisonsTest do
  @moduledoc """
  The Train comparisons as the pages read them: the final test's totals, the
  cases' changes and the verdict are worked out from the data, every comparison in the
  folder is read, newest first, a download is the file's own bytes, and a name
  the folder has no file for is not found. The comparisons are written by
  `Techtree.TrainFixture` into a folder of each test's own, except the last
  test, which reads the committed folder.
  """

  use ExUnit.Case, async: true
  use ExUnitProperties

  alias Techtree.Catalog.Digest
  alias Techtree.Train.Comparisons
  alias Techtree.TrainFixture

  describe "one folder" do
    @describetag :tmp_dir

    property "the totals and changes are the cases' own", %{tmp_dir: folder} do
      check all(
              better <- integer(0..20),
              same <- integer(0..20),
              worse <- integer(0..20),
              better + same + worse > 0
            ) do
        TrainFixture.write!(folder, "counted", changes: {better, same, worse})
        {:ok, comparison} = Comparisons.fetch("counted", folder)
        cases = better + same + worse

        assert comparison.changes == %{better: better, same: same, worse: worse}
        assert comparison.final.original == %{solved: same + 3 * worse, attempts: 3 * cases}

        assert comparison.final.improved == %{
                 solved: 2 * better + same + 2 * worse,
                 attempts: 3 * cases
               }

        assert length(comparison.cases) == cases
      end
    end

    test "the working and choosing figures are attempts out of each step's cases",
         %{tmp_dir: folder} do
      TrainFixture.write!(folder, "steps")

      assert {:ok, %{start: start, choosing: choosing, split: split}} =
               Comparisons.fetch("steps", folder)

      assert split == %{working: 10, choosing: 8, final: 38}
      assert start.original == %{solved: 9, attempts: 30}
      assert choosing.revision == %{solved: 15, attempts: 24}
      assert choosing.rewrite == %{solved: 10, attempts: 24}
    end

    property "the verdict follows the chance reading, then the final test's totals",
             %{tmp_dir: folder} do
      check all(
              better <- integer(0..20),
              same <- integer(0..20),
              worse <- integer(0..20),
              better + same + worse > 0,
              p_value <- float(min: 0.0, max: 1.0),
              selected <- member_of(["rewrite", "revision"])
            ) do
        TrainFixture.write!(folder, "judged",
          changes: {better, same, worse},
          p_value: p_value,
          selected: selected
        )

        {:ok, %{final: final} = comparison} = Comparisons.fetch("judged", folder)

        expected =
          cond do
            p_value >= 0.05 -> :inconclusive
            final.improved.solved > final.original.solved -> :improved
            true -> :worse
          end

        assert comparison.verdict == expected
        assert comparison.selected == String.to_existing_atom(selected)
      end
    end

    test "every comparison is listed, newest first, then by slug", %{tmp_dir: folder} do
      TrainFixture.write!(folder, "older", date: "2026-11-09")
      TrainFixture.write!(folder, "newest", date: "2026-11-14")
      TrainFixture.write!(folder, "same-day-b", date: "2026-11-10")
      TrainFixture.write!(folder, "same-day-a", date: "2026-11-10")

      assert Enum.map(Comparisons.list(folder), & &1.slug) ==
               ["newest", "same-day-a", "same-day-b", "older"]
    end

    test "a folder with no comparisons, or no folder at all, lists none", %{tmp_dir: folder} do
      assert Comparisons.list(folder) == []
      assert Comparisons.list(Path.join(folder, "not-there")) == []
    end

    test "a download is the file's exact bytes and their digest", %{tmp_dir: folder} do
      TrainFixture.write!(folder, "example")
      report = File.read!(Path.join(folder, "example.json"))

      assert Comparisons.download("example", folder) == {:ok, report, Digest.hash_bytes(report)}
    end

    test "a name the folder has no comparison for is not found", %{tmp_dir: folder} do
      TrainFixture.write!(folder, "example")

      for slug <- ["missing", "../example", "example.json", "EXAMPLE"] do
        assert Comparisons.fetch(slug, folder) == :error
        assert Comparisons.download(slug, folder) == :error
      end
    end
  end

  test "every comparison committed for the release reads" do
    assert [_ | _] = comparisons = Comparisons.list()

    for comparison <- comparisons do
      assert Comparisons.fetch(comparison.slug) == {:ok, comparison}
    end
  end
end
