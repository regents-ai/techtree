defmodule Techtree.Train.ComparisonsTest do
  @moduledoc """
  The Train comparisons as the pages read them: the final test's totals and
  the cases' changes are counted from the cases, every comparison in the
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
      assert choosing.improved == %{solved: 15, attempts: 24}
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
