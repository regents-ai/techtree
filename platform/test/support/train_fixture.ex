defmodule Techtree.TrainFixture do
  @moduledoc """
  Train comparisons made for the tests, in the shape
  `Techtree.Train.Comparisons` reads, written into a folder of the test's own:

      write!(folder, "older", date: "2026-11-09")
      write!(folder, "mixed", changes: {5, 3, 2})
      write!(folder, "unclear", selected: "rewrite", p_value: 0.4)
  """

  @repeats 3

  @doc """
  The bytes of one comparison file.

  Options: `:date` (ISO 8601, default `"2026-11-14"`), `:changes`
  (`{better, same, worse}` final-test cases, default `{25, 12, 1}`),
  `:selected` (`"revision"` or `"rewrite"`, default `"revision"`; the one
  selected solves the most at the choosing step) and `:p_value` (default
  `0.01`, against a chance level of `0.05`).
  """
  @spec report(keyword()) :: binary()
  def report(opts \\ []) do
    {better, same, worse} = Keyword.get(opts, :changes, {25, 12, 1})
    selected = Keyword.get(opts, :selected, "revision")
    {rewrite, revision} = if selected == "revision", do: {10, 15}, else: {15, 10}

    final =
      (List.duplicate({0, 2}, better) ++
         List.duplicate({1, 1}, same) ++ List.duplicate({3, 2}, worse))
      |> Enum.with_index()
      |> Enum.map(fn {{original, improved}, index} ->
        %{"case" => "case-#{index}", "original" => original, "improved" => improved}
      end)

    Jason.encode!(%{
      "schema_version" => "techtree.train.v1alpha3",
      "kind" => "Comparison",
      "date" => Keyword.get(opts, :date, "2026-11-14"),
      "skill" => %{
        "name" => "Example",
        "maker" => "Example Maker",
        "collection" => "examples",
        "license" => "MIT",
        "summary" => "A Skill made for the tests.",
        "github_url" => "https://github.com/example/skills/tree/main/example",
        "skills_sh_url" => "https://skills.sh/example/skills/example"
      },
      "task" => "Reply with the answer the case asks for.",
      "agent" => %{
        "maker" => "NVIDIA",
        "name" => "Nemotron 3 Nano 4B",
        "model" => "nemotron-3-nano:4b"
      },
      "scorer" => %{"maker" => "Prime Intellect", "name" => "Verifiers", "version" => "0.4.1"},
      "checker" => %{"maker" => "NVIDIA", "name" => "SkillEvaluator", "version" => "0.9.0"},
      "rewriter" => %{"maker" => "Anthropic", "name" => "Claude Opus 5.5"},
      "reviser" => %{"maker" => "Microsoft", "name" => "SkillOpt"},
      "proposer" => %{"maker" => "Anthropic", "name" => "Claude Opus 5.5"},
      "selected" => selected,
      "repeats" => @repeats,
      "cases" => %{"working" => 10, "choosing" => 8, "final" => length(final)},
      "start" => %{"no_skill" => 3, "original" => 9},
      "choosing" => %{"original" => 6, "rewrite" => rewrite, "revision" => revision},
      "final" => final,
      "p_value" => Keyword.get(opts, :p_value, 0.01),
      "chance_level" => 0.05
    })
  end

  @doc "Write one comparison into `folder` under `slug`."
  @spec write!(Path.t(), String.t(), keyword()) :: :ok
  def write!(folder, slug, opts \\ []) do
    File.mkdir_p!(folder)
    File.write!(Path.join(folder, slug <> ".json"), report(opts))
  end
end
