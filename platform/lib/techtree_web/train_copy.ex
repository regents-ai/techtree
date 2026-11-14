defmodule TechtreeWeb.TrainCopy do
  @moduledoc """
  The words and figures of a comparison, shared by its page, its Markdown
  (`TechtreeWeb.TrainMD`), Results and the home page, so all of them say the
  same thing.

  There is one measure: attempts solved, as a whole percentage with the count
  beside it ("35%, 40 of 114"). The two versions are named Original and
  Improved.
  """

  alias Techtree.Train.Comparisons

  @doc "A share of attempts solved as a whole percentage: 40 of 114 is \"35%\"."
  @spec percent(Comparisons.side()) :: String.t()
  def percent(%{solved: solved, attempts: attempts}), do: "#{round(solved * 100 / attempts)}%"

  @doc "Attempts solved as a count: \"40 of 114\"."
  @spec count(Comparisons.side()) :: String.t()
  def count(%{solved: solved, attempts: attempts}), do: "#{solved} of #{attempts}"

  @doc "Attempts solved in full: \"35%, 40 of 114\"."
  @spec figure(Comparisons.side()) :: String.t()
  def figure(side), do: "#{percent(side)}, #{count(side)}"

  @doc "One case's attempts solved: \"2 of 3\"."
  @spec solved(non_neg_integer(), pos_integer()) :: String.t()
  def solved(solved, repeats), do: "#{solved} of #{repeats}"

  @doc "One case's change in attempts solved, signed: \"+2\", \"0\" or \"−1\"."
  @spec change(Comparisons.final_case()) :: String.t()
  def change(%{original: original, improved: improved}), do: signed(improved - original)

  @doc "How many more attempts the improved version solved: \"+52 attempts\"."
  @spec difference(Comparisons.t()) :: String.t()
  def difference(%{final: %{original: original, improved: improved}}),
    do: "#{signed(improved.solved - original.solved)} attempts"

  @doc "The cases by change: \"25 better, 12 the same, 1 worse\"."
  @spec changes(Comparisons.t()) :: String.t()
  def changes(%{changes: %{better: better, same: same, worse: worse}}),
    do: "#{better} better, #{same} the same, #{worse} worse"

  @doc "The cases that did worse, named with their figures, or that none did."
  @spec worse(Comparisons.t()) :: String.t()
  def worse(%{cases: cases, repeats: repeats}) do
    case Enum.filter(cases, &(&1.change == :worse)) do
      [] ->
        "No case did worse with the improved Skill."

      [one] ->
        "One case did worse with the improved Skill: #{went(one, repeats)}."

      worse ->
        "#{length(worse)} cases did worse with the improved Skill: " <>
          Enum.map_join(worse, "; ", &went(&1, repeats)) <> "."
    end
  end

  @doc """
  The chance reading in a sentence: how rarely a difference this large would
  turn up if the two versions were equally good.
  """
  @spec chance(Comparisons.t()) :: String.t()
  def chance(%{p_below: p_below}) do
    "If the two versions were equally good, a difference this large would turn up by chance " <>
      "fewer than 1 time in #{number(round(1 / p_below))}."
  end

  @doc "The chance reading as a short figure: \"Under 1 in 1,000\"."
  @spec odds(Comparisons.t()) :: String.t()
  def odds(%{p_below: p_below}), do: "Under 1 in #{number(round(1 / p_below))}"

  @doc "Where the Skill comes from and what this is, in two sentences."
  @spec provenance(Comparisons.t()) :: String.t()
  def provenance(%{skill: skill}) do
    "A demonstration Techtree ran itself on #{skill.maker}’s public #{skill.name} Skill, from its " <>
      "#{skill.collection} collection (#{skill.license} license), used unchanged as the starting point. " <>
      "It is not customer work."
  end

  @doc "The final test in a sentence."
  @spec final_test(Comparisons.t()) :: String.t()
  def final_test(%{split: split, repeats: repeats, final: %{original: side}}) do
    "The final test: #{split.final} cases nothing had seen, each asked #{repeats} times of each version, " <>
      "#{side.attempts} attempts per side."
  end

  @doc """
  The method, step by step: `{title, words, choices}`, where `choices` is the
  versions tried at that step, in order, as `{name, side}`; only the choosing
  step has any.
  """
  @spec method(Comparisons.t()) :: [
          {String.t(), String.t(), [{String.t(), Comparisons.side()}]}
        ]
  def method(comparison) do
    %{split: split, repeats: repeats, start: start, choosing: choosing, final: final} = comparison
    total = split.working + split.choosing + split.final

    [
      {"Split",
       "We wrote #{total} cases for this test and split them once, before anything ran: " <>
         "#{split.working} to work on the Skill, #{split.choosing} to choose between versions and " <>
         "#{split.final} kept apart for the final test. Every version was asked each case #{repeats} times.",
       []},
      {"Improve",
       "#{possessive(comparison.improver)}, with #{possessive(comparison.proposer)} proposing the changes, " <>
         "improved the Skill using only the #{split.working} working cases. On those cases the agent " <>
         "solved #{percent(start.no_skill)} of its attempts with no Skill (#{count(start.no_skill)}) and " <>
         "#{percent(start.original)} with the original (#{count(start.original)}).", []},
      {"Choose",
       "Three versions were tried on the #{split.choosing} choosing cases: the original, a single plain " <>
         "rewrite and #{comparison.improver.name}’s revision. The revision solved the most and became the improved Skill.",
       [
         {"Original", choosing.original},
         {"Rewrite", choosing.rewrite},
         {"Improved", choosing.improved}
       ]},
      {"Final test",
       "One run on the #{split.final} cases nothing had seen, #{final.original.attempts} attempts per version, " <>
         "with the same agent and settings on both sides.", []}
    ]
  end

  @doc "The tools and what each did: `{term, words}`."
  @spec tools(Comparisons.t()) :: [{String.t(), String.t()}]
  def tools(comparison) do
    %{agent: agent, scorer: scorer, skill: skill} = comparison

    [
      {"Agent", "#{possessive(agent)} (#{agent.model}), run on our own machine."},
      {"Scoring",
       "#{possessive(scorer)} #{scorer.version}, with the same settings on both sides."},
      {"Improver", "#{possessive(comparison.improver)}, on the working cases only."},
      {"Changes",
       "#{possessive(comparison.proposer)}, proposing #{comparison.improver.name}’s changes."},
      {"Skill",
       "#{skill.maker}’s #{skill.name} Skill, the starting point, #{skill.license} license."}
    ]
  end

  @doc "A tool named with its maker: \"NVIDIA’s Nemotron 3 Nano 4B\"."
  @spec possessive(%{maker: String.t(), name: String.t()}) :: String.t()
  def possessive(%{maker: maker, name: name}), do: "#{maker}’s #{name}"

  @doc "A day, as the site writes one: \"14 Nov 2026\"."
  @spec date(Date.t()) :: String.t()
  def date(date), do: Calendar.strftime(date, "%-d %b %Y")

  defp went(%{id: id, original: original, improved: improved}, repeats),
    do: "#{id} went from #{solved(original, repeats)} to #{solved(improved, repeats)}"

  defp signed(0), do: "0"
  defp signed(value) when value > 0, do: "+#{value}"
  defp signed(value), do: "−#{-value}"

  defp number(value) do
    value
    |> Integer.to_string()
    |> String.reverse()
    |> String.replace(~r/(\d{3})(?=\d)/, "\\1,")
    |> String.reverse()
  end
end
