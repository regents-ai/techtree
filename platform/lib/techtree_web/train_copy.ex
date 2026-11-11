defmodule TechtreeWeb.TrainCopy do
  @moduledoc """
  The words and figures of the Train pages, shared by their HTML and their
  Markdown (`TechtreeWeb.Plugs.PageMarkdown`), so both say the same thing.

  An arm is named by the change it carries: without and with the Skill, or
  before and after RL. Mean rewards are shown as percentages and their
  difference in points, rounded to whole numbers.
  """

  alias Techtree.Train.Comparisons

  @doc "One arm's name on the page."
  @spec arm_label(Comparisons.t(), Comparisons.arm()) :: String.t()
  def arm_label(%{change: :skill}, %{change: :none}), do: "Without Skill"
  def arm_label(%{change: :skill}, %{change: :skill}), do: "With Skill"
  def arm_label(%{change: :rl}, %{change: :none}), do: "Before RL"
  def arm_label(%{change: :rl}, %{change: :rl}), do: "After RL"

  @doc "The change a comparison measures, as a word."
  @spec change(Comparisons.change()) :: String.t()
  def change(:skill), do: "Skill"
  def change(:rl), do: "RL"

  @doc "A comparison's outcome, as a word."
  @spec outcome(Comparisons.outcome()) :: String.t()
  def outcome(:uplift), do: "Uplift"
  def outcome(:tie), do: "Tie"
  def outcome(:regression), do: "Regression"
  def outcome(:inconclusive), do: "Inconclusive"

  @doc "The status tone of an outcome."
  @spec tone(Comparisons.outcome()) :: String.t()
  def tone(:uplift), do: "success"
  def tone(:tie), do: "neutral"
  def tone(:regression), do: "error"
  def tone(:inconclusive), do: "warning"

  @doc "A task's result for the changed arm, as a word."
  @spec result(Comparisons.result()) :: String.t()
  def result(:win), do: "Win"
  def result(:tie), do: "Tie"
  def result(:loss), do: "Loss"

  @doc "A mean reward as a whole percentage: 0.40625 is \"41%\"."
  @spec percent(number()) :: String.t()
  def percent(reward), do: "#{round(reward * 100)}%"

  @doc "A difference of rewards in whole points, signed: 0.37 is \"+37\"."
  @spec points(number()) :: String.t()
  def points(difference) do
    case round(difference * 100) do
      0 -> "0"
      points when points > 0 -> "+#{points}"
      points -> "−#{-points}"
    end
  end

  @doc "The 95% interval of the difference, in points: \"+28 to +46\"."
  @spec interval({number(), number()}) :: String.t()
  def interval({low, high}), do: "#{points(low)} to #{points(high)}"

  @doc "A reward on one task, to two places."
  @spec reward(number()) :: String.t()
  def reward(value), do: :erlang.float_to_binary(value / 1, decimals: 2)

  @doc "The paired results in one line: \"30 wins · 28 ties · 6 losses\"."
  @spec paired(%{wins: integer(), ties: integer(), losses: integer()}) :: String.t()
  def paired(%{wins: wins, ties: ties, losses: losses}),
    do: "#{count(wins, "win", "wins")} · #{count(ties, "tie", "ties")} · #{count(losses, "loss", "losses")}"

  @doc "How many tasks an arm solved: \"26 of 64 solved\"."
  @spec solved(Comparisons.arm(), pos_integer()) :: String.t()
  def solved(%{solved: solved}, task_count), do: "#{solved} of #{task_count} solved"

  @doc "The task split, as a word."
  @spec split(String.t()) :: String.t()
  def split("held_out"), do: "Held out"

  @doc "A whole number with thousands separated: 41216 is \"41,216\"."
  @spec number(integer()) :: String.t()
  def number(value) when is_integer(value) do
    value
    |> Integer.to_string()
    |> String.reverse()
    |> String.replace(~r/(\d{3})(?=\d)/, "\\1,")
    |> String.reverse()
  end

  @doc "A run's length: \"42 min\" or \"2 h 5 min\"."
  @spec duration(number()) :: String.t()
  def duration(seconds) do
    minutes = round(seconds / 60)

    case {div(minutes, 60), rem(minutes, 60)} do
      {0, 0} -> "#{round(seconds)} s"
      {0, minutes} -> "#{minutes} min"
      {hours, 0} -> "#{hours} h"
      {hours, minutes} -> "#{hours} h #{minutes} min"
    end
  end

  @doc "A day, as the site writes one: \"10 Nov 2026\"."
  @spec date(DateTime.t()) :: String.t()
  def date(datetime), do: Calendar.strftime(datetime, "%-d %b %Y")

  @doc "A time to the minute, in UTC: \"10 Nov 2026, 09:42 UTC\"."
  @spec time(DateTime.t()) :: String.t()
  def time(datetime), do: Calendar.strftime(datetime, "%-d %b %Y, %H:%M UTC")

  @doc "The email that asks about private training: to build@regents.sh, with what it needs."
  @spec private_mailto() :: String.t()
  def private_mailto do
    body = Enum.join(["Company:", "Your tasks:", "Model:", "How a result is scored:"], "\r\n")
    "mailto:build@regents.sh?" <> URI.encode_query([subject: "Techtree Private Training", body: body], :rfc3986)
  end

  defp count(1, one, _many), do: "1 #{one}"
  defp count(count, _one, many), do: "#{count} #{many}"
end
