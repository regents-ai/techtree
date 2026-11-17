defmodule TechtreeWeb.TrainMD do
  @moduledoc """
  A comparison's page as Markdown, the same figures and words as its HTML
  (`TechtreeWeb.TrainCopy`), answered at the page's own address
  (`TechtreeWeb.Plugs.PageMarkdown`).
  """

  use TechtreeWeb, :verified_routes

  alias TechtreeWeb.TrainCopy, as: Copy

  @doc "`/train/:slug`: one comparison in full."
  @spec show(Techtree.Train.Comparisons.t()) :: String.t()
  def show(comparison) do
    %{skill: skill, final: final, repeats: repeats} = comparison

    method =
      comparison
      |> Copy.method()
      |> Enum.with_index(1)
      |> Enum.map_join("\n", fn {{title, words, choices}, index} ->
        figures =
          Enum.map_join(choices, fn {name, side, _chosen} ->
            "\n   - #{name}: #{Copy.figure(side)}"
          end)

        "#{index}. #{title}: #{words}#{figures}"
      end)

    cases =
      Enum.map_join(comparison.cases, "\n", fn item ->
        "| `#{item.id}` | #{Copy.solved(item.original, repeats)} | " <>
          "#{Copy.solved(item.improved, repeats)} | #{Copy.change(item)} |"
      end)

    tools =
      Enum.map_join(Copy.tools(comparison), "\n", fn {term, words} -> "- #{term}: #{words}" end)

    """
    # #{skill.name}

    #{skill.summary} [GitHub](#{skill.github_url}) · [skills.sh](#{skill.skills_sh_url})

    #{Copy.provenance(comparison)} #{Copy.date(comparison.date)}.

    ## Task

    #{comparison.task}

    ## Result

    #{Copy.final_test(comparison)}

    - Original: #{Copy.figure(final.original)}
    - Revised: #{Copy.figure(final.improved)}
    - Verdict: #{Copy.verdict_name(comparison)}
    - Difference: #{Copy.difference(comparison)}
    - Cases: #{Copy.changes(comparison)}
    - Chance: #{Copy.odds(comparison)}

    #{Copy.verdict(comparison)} #{Copy.chance(comparison)}

    ## Method

    #{method}

    ## Cases

    #{Copy.worse(comparison)}

    | Case | Original | Revised | Change |
    | --- | --- | --- | --- |
    #{cases}

    ## Tools

    #{tools}

    ## Report

    The report lists every final-test case with the attempts each version solved: [download](#{url(~p"/train/#{comparison.slug}/report.json")}). [How to check it](#{url(~p"/docs/verify")}#blog-section-skill-comparisons).
    """
  end
end
