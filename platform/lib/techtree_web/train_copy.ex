defmodule TechtreeWeb.TrainCopy do
  @moduledoc """
  The words and figures of a comparison, shared by its page, its Markdown
  (`TechtreeWeb.TrainMD`), Results and the home page, so all of them say the
  same thing.

  There is one measure: attempts solved, as a whole percentage with the count
  beside it ("35%, 40 of 114"). The two versions are named Original and
  Improved, the improved Skill being the revision chosen to improve it, and
  every sentence about the outcome follows the comparison's verdict, so one
  that did not help says so.
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

  @doc ~s(One case's change in attempts solved, signed: "+2", "0" or "−1".)
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

  @doc ~s(The verdict in its one word: "Improved", "Inconclusive" or "Worse".)
  @spec verdict_name(Comparisons.t()) :: String.t()
  def verdict_name(%{verdict: :improved}), do: "Improved"
  def verdict_name(%{verdict: :inconclusive}), do: "Inconclusive"
  def verdict_name(%{verdict: :worse}), do: "Worse"

  @doc """
  The verdict in a sentence: what the improved Skill did on the final test
  against the original, and whether chance explains it. One that did not help
  says so first: "did not help" when it solved no more, "did not clearly help"
  when it solved more but within chance.
  """
  @spec verdict(Comparisons.t()) :: String.t()
  def verdict(%{final: %{original: original, improved: improved}} = comparison) do
    difference = improved.solved - original.solved

    did =
      "#{sentence_start(revision(comparison))} solved #{more_or_fewer(difference)} than the original"

    case comparison.verdict do
      :inconclusive ->
        "#{did_not_help(difference)} #{did}, a difference within chance: " <>
          "these cases cannot tell the two versions apart."

      :worse ->
        "The change did not help. #{did}, more than chance explains."

      :improved ->
        "#{did}, more than chance explains."
    end
  end

  defp did_not_help(difference) when difference > 0, do: "The change did not clearly help."
  defp did_not_help(_difference), do: "The change did not help."

  @doc """
  The chance reading in a sentence: how often a difference this large would
  turn up if the two versions were equally good, against the line agreed
  before anything ran.
  """
  @spec chance(Comparisons.t()) :: String.t()
  def chance(%{p_value: p_value, chance_level: level} = comparison) do
    side = if comparison.verdict == :inconclusive, do: "within", else: "beyond"

    "If the two versions were equally good, a difference this large would turn up by chance " <>
      "#{how_often(p_value)}. The line agreed before anything ran is #{per_hundred(level)} in 100, " <>
      "so this difference is #{side} chance."
  end

  @doc ~s(The chance reading as a short figure: "Under 1 in 1,000" or "About 74.5 in 100".)
  @spec odds(Comparisons.t()) :: String.t()
  def odds(%{p_value: p_value}) when p_value < 0.001, do: "Under 1 in 1,000"
  def odds(%{p_value: p_value}), do: "About #{per_hundred(p_value)} in 100"

  @doc ~s(The improved Skill by what it is: "the plain rewrite" or "Microsoft’s SkillOpt revision".)
  @spec revision(Comparisons.t()) :: String.t()
  def revision(%{selected: :rewrite}), do: "the plain rewrite"
  def revision(%{selected: :revision, reviser: reviser}), do: "#{possessive(reviser)} revision"

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
  versions tried at that step, in order, as `{name, side, chosen?}`; only the
  choosing step has any.
  """
  @spec method(Comparisons.t()) :: [
          {String.t(), String.t(), [{String.t(), Comparisons.side(), boolean()}]}
        ]
  def method(comparison) do
    %{split: split, repeats: repeats, start: start, choosing: choosing, final: final} = comparison
    %{rewriter: rewriter, reviser: reviser, proposer: proposer, selected: selected} = comparison
    total = split.working + split.choosing + split.final

    [
      {"Split",
       "We wrote #{total} cases for this test and split them once, before anything ran: " <>
         "#{split.working} to work on the Skill, #{split.choosing} to choose between versions and " <>
         "#{split.final} kept apart for the final test. Every version was asked each case #{repeats} times.",
       []},
      {"Improve",
       "Two revisions were made from the #{split.working} working cases alone: a single plain rewrite " <>
         "by #{possessive(rewriter)}, and a revision by #{possessive(reviser)}, with " <>
         "#{possessive(proposer)} proposing its changes. On those cases the agent solved " <>
         "#{percent(start.no_skill)} of its attempts with no Skill (#{count(start.no_skill)}) and " <>
         "#{percent(start.original)} with the original (#{count(start.original)}).", []},
      {"Choose",
       "The original and both revisions were tried on the #{split.choosing} choosing cases. " <>
         "#{sentence_start(revision(comparison))} solved the most and became the improved Skill.",
       [
         {"Original", choosing.original, false},
         {"Rewrite", choosing.rewrite, selected == :rewrite},
         {reviser.name, choosing.revision, selected == :revision}
       ]},
      {"Final test",
       "One run on the #{split.final} cases nothing had seen, #{final.original.attempts} attempts per version, " <>
         "with the same agent and settings on both sides.", []}
    ]
  end

  @doc "The tools and what each did: `{term, words}`."
  @spec tools(Comparisons.t()) :: [{String.t(), String.t()}]
  def tools(comparison) do
    %{agent: agent, scorer: scorer, checker: checker, skill: skill} = comparison

    [
      {"Agent", "#{possessive(agent)} (#{agent.model}), run on our own machine."},
      {"Scoring",
       "#{possessive(scorer)} #{scorer.version}, with the same settings on both sides."},
      {"Check",
       "#{possessive(checker)} #{checker.version} reviewed the original Skill as written."},
      {"Rewrite",
       "#{possessive(comparison.rewriter)}, one plain rewrite from the working cases."},
      {"Revision",
       "#{possessive(comparison.reviser)}, with #{possessive(comparison.proposer)} proposing its " <>
         "changes, on the working cases only."},
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

  defp sentence_start(<<first::utf8, rest::binary>>), do: String.upcase(<<first::utf8>>) <> rest

  defp more_or_fewer(difference) when difference >= 0,
    do: "#{difference} more #{attempts(difference)}"

  defp more_or_fewer(difference), do: "#{-difference} fewer #{attempts(-difference)}"

  defp attempts(1), do: "attempt"
  defp attempts(_count), do: "attempts"

  # How often chance alone would give the difference: rarer than 1 in 1,000,
  # or about so many in 100, to one decimal place.
  defp how_often(p_value) when p_value < 0.001, do: "fewer than 1 time in 1,000"
  defp how_often(p_value), do: "about #{per_hundred(p_value)} times in 100"

  defp per_hundred(share) do
    case Float.round(share * 100.0, 1) do
      whole when whole == trunc(whole) -> Integer.to_string(trunc(whole))
      fraction -> Float.to_string(fraction)
    end
  end

  defp signed(0), do: "0"
  defp signed(value) when value > 0, do: "+#{value}"
  defp signed(value), do: "−#{-value}"
end
