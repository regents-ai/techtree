defmodule Techtree.Train.Comparisons do
  @moduledoc """
  The comparisons the site shows: a public Skill as it was published (the
  original) against the version chosen to improve it (the improved Skill), on
  final-test cases kept apart before anything ran, each case asked the same
  number of times of each version by the same agent with the same settings,
  and counted in attempts solved.

  Two revisions are made from the working cases: a single plain rewrite, and
  a revision by an automatic tool whose changes a model proposes. The three
  versions are measured on the choosing cases, and the revision that solved
  the most there, which must also beat the original, is the improved Skill
  (`selected`).

  Each comparison is one `<slug>.json` in the configured folder
  (`config :techtree, #{inspect(__MODULE__)}, folder: ...`, as
  `{:priv, subdirectory}` for the copy shipped in the release or as a plain
  path), `techtree.train.v1alpha3`, kind `Comparison`, named by its slug.

  Every field the pages draw is matched exactly: a missing or different field
  raises rather than drawing something else. The final test's totals, the
  difference and the cases that did better, the same and worse are counted
  from its cases, never taken from the file, and so is the verdict: Improved
  or Worse when the difference is beyond chance (`p_value` under
  `chance_level`), Inconclusive when it is not.
  """

  alias Techtree.Catalog.Digest

  @schema_version "techtree.train.v1alpha3"
  @kind "Comparison"
  @revisions %{"rewrite" => :rewrite, "revision" => :revision}

  @slug ~r/\A[a-z0-9]+(?:-[a-z0-9]+)*\z/

  @type side :: %{solved: non_neg_integer(), attempts: pos_integer()}
  @type change :: :better | :same | :worse
  @type verdict :: :improved | :inconclusive | :worse
  @type revision :: :rewrite | :revision
  @type final_case :: %{
          id: String.t(),
          original: non_neg_integer(),
          improved: non_neg_integer(),
          change: change()
        }
  @type tool :: %{maker: String.t(), name: String.t()}

  @type t :: %{
          slug: String.t(),
          date: Date.t(),
          skill: %{
            name: String.t(),
            maker: String.t(),
            collection: String.t(),
            license: String.t(),
            summary: String.t(),
            github_url: String.t(),
            skills_sh_url: String.t()
          },
          task: String.t(),
          agent: %{maker: String.t(), name: String.t(), model: String.t()},
          scorer: %{maker: String.t(), name: String.t(), version: String.t()},
          checker: %{maker: String.t(), name: String.t(), version: String.t()},
          rewriter: tool(),
          reviser: tool(),
          proposer: tool(),
          selected: revision(),
          repeats: pos_integer(),
          split: %{working: pos_integer(), choosing: pos_integer(), final: pos_integer()},
          start: %{no_skill: side(), original: side()},
          choosing: %{original: side(), rewrite: side(), revision: side()},
          final: %{original: side(), improved: side()},
          cases: [final_case()],
          changes: %{better: non_neg_integer(), same: non_neg_integer(), worse: non_neg_integer()},
          p_value: number(),
          chance_level: number(),
          verdict: verdict()
        }

  @doc "The configured folder of comparisons."
  @spec folder() :: Path.t()
  def folder do
    case Application.fetch_env!(:techtree, __MODULE__) |> Keyword.fetch!(:folder) do
      {:priv, subdirectory} -> Application.app_dir(:techtree, ["priv", subdirectory])
      path when is_binary(path) -> path
    end
  end

  @doc "Every comparison in `folder`, newest first, then by slug."
  @spec list(Path.t()) :: [t()]
  def list(folder \\ folder()) do
    folder
    |> slugs()
    |> Enum.map(&comparison(&1, report(folder, &1)))
    |> Enum.sort_by(& &1.date, {:desc, Date})
  end

  @doc """
  One comparison by its slug, or `:error` when the folder has none by that
  name. The slug is looked up among the folder's own files, never used as a
  path.
  """
  @spec fetch(String.t(), Path.t()) :: {:ok, t()} | :error
  def fetch(slug, folder \\ folder()) do
    with {:ok, slug} <- listed(folder, slug),
         do: {:ok, comparison(slug, report(folder, slug))}
  end

  @doc "The exact bytes of one comparison's file with the digest of those bytes."
  @spec download(String.t(), Path.t()) :: {:ok, binary(), String.t()} | :error
  def download(slug, folder \\ folder()) do
    with {:ok, slug} <- listed(folder, slug) do
      bytes = report(folder, slug)
      %{slug: ^slug} = comparison(slug, bytes)
      {:ok, bytes, Digest.hash_bytes(bytes)}
    end
  end

  defp listed(folder, slug) do
    if slug in slugs(folder), do: {:ok, slug}, else: :error
  end

  # The folder's comparisons, by the name of each `.json` file in it, in slug
  # order. A folder that is not there yet has none.
  defp slugs(folder) do
    folder
    |> Path.join("*.json")
    |> Path.wildcard()
    |> Enum.map(fn path ->
      slug = Path.basename(path, ".json")
      true = Regex.match?(@slug, slug)
      slug
    end)
    |> Enum.sort()
  end

  # The slug is one of the folder's own file names (`slugs/1`).
  # sobelow_skip ["Traversal.FileModule"]
  defp report(folder, slug), do: File.read!(Path.join(folder, slug <> ".json"))

  defp comparison(slug, bytes) do
    %{
      "schema_version" => @schema_version,
      "kind" => @kind,
      "date" => date,
      "skill" => skill,
      "task" => task,
      "agent" => agent,
      "scorer" => scorer,
      "checker" => checker,
      "rewriter" => rewriter,
      "reviser" => reviser,
      "proposer" => proposer,
      "selected" => selected,
      "repeats" => repeats,
      "cases" => %{"working" => working, "choosing" => choosing_count, "final" => final_count},
      "start" => %{"no_skill" => no_skill, "original" => start_original},
      "choosing" => %{"original" => original, "rewrite" => rewrite, "revision" => revision},
      "final" => final,
      "p_value" => p_value,
      "chance_level" => chance_level
    } = Jason.decode!(bytes)

    true =
      Enum.all?([repeats, working, choosing_count, final_count], &(is_integer(&1) and &1 > 0))

    true = is_number(p_value) and p_value >= 0 and p_value <= 1
    true = is_number(chance_level) and chance_level > 0 and chance_level < 1
    true = text?(task)

    cases = cases(final, final_count, repeats)

    choosing = %{
      original: side(original, choosing_count, repeats),
      rewrite: side(rewrite, choosing_count, repeats),
      revision: side(revision, choosing_count, repeats)
    }

    selected = Map.fetch!(@revisions, selected)
    true = chosen?(choosing, selected)

    final_sides = %{
      original: total(cases, :original, repeats),
      improved: total(cases, :improved, repeats)
    }

    %{
      slug: slug,
      date: Date.from_iso8601!(date),
      skill:
        texts(skill, ~w(name maker collection license summary github_url skills_sh_url)a)
        |> links(),
      task: task,
      agent: texts(agent, ~w(maker name model)a),
      scorer: texts(scorer, ~w(maker name version)a),
      checker: texts(checker, ~w(maker name version)a),
      rewriter: texts(rewriter, ~w(maker name)a),
      reviser: texts(reviser, ~w(maker name)a),
      proposer: texts(proposer, ~w(maker name)a),
      selected: selected,
      repeats: repeats,
      split: %{working: working, choosing: choosing_count, final: final_count},
      start: %{
        no_skill: side(no_skill, working, repeats),
        original: side(start_original, working, repeats)
      },
      choosing: choosing,
      final: final_sides,
      cases: cases,
      changes:
        Map.new([:better, :same, :worse], &{&1, Enum.count(cases, fn c -> c.change == &1 end)}),
      p_value: p_value,
      chance_level: chance_level,
      verdict: verdict(final_sides, p_value, chance_level)
    }
  end

  # The improved Skill is the revision that solved the most choosing attempts,
  # more than the original and more than the other revision.
  defp chosen?(choosing, selected) do
    [other] = Map.values(@revisions) -- [selected]
    best = choosing[selected].solved
    best > choosing.original.solved and best > choosing[other].solved
  end

  # Beyond chance, the difference's direction decides; within it, nothing does.
  defp verdict(_final, p_value, chance_level) when p_value >= chance_level, do: :inconclusive

  defp verdict(%{original: %{solved: original}, improved: %{solved: improved}}, _p, _level),
    do: if(improved > original, do: :improved, else: :worse)

  # One entry per final-test case, each named once, with how many of its
  # attempts each version solved.
  defp cases(final, count, repeats) do
    cases =
      Enum.map(final, fn %{"case" => id, "original" => original, "improved" => improved} ->
        true = text?(id) and solved?(original, repeats) and solved?(improved, repeats)
        %{id: id, original: original, improved: improved, change: change(original, improved)}
      end)

    ^count = length(cases)
    ^count = cases |> Enum.uniq_by(& &1.id) |> length()
    cases
  end

  defp change(original, improved) when improved > original, do: :better
  defp change(original, improved) when improved < original, do: :worse
  defp change(_original, _improved), do: :same

  defp total(cases, version, repeats),
    do: %{
      solved: cases |> Enum.map(&Map.fetch!(&1, version)) |> Enum.sum(),
      attempts: length(cases) * repeats
    }

  defp side(solved, cases, repeats) do
    attempts = cases * repeats
    true = solved?(solved, attempts)
    %{solved: solved, attempts: attempts}
  end

  defp texts(map, keys) do
    Map.new(keys, fn key ->
      value = Map.fetch!(map, Atom.to_string(key))
      true = text?(value)
      {key, value}
    end)
  end

  defp links(
         %{github_url: "https://github.com/" <> _, skills_sh_url: "https://skills.sh/" <> _} =
           skill
       ),
       do: skill

  defp text?(value), do: is_binary(value) and value != ""
  defp solved?(value, attempts), do: is_integer(value) and value >= 0 and value <= attempts
end
