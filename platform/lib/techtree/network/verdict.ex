defmodule Techtree.Network.Verdict do
  @moduledoc """
  What one published Result can say about its Skill change, and how sure it is.

  Two things must both hold before a Result says "improved" or "regressed".
  The change must clear its Campaign's rule, which `Techtree.Network.Result`
  recorded as the Result's `Techtree.Network.Assessment` reason. And the tasks
  that moved must mostly move the same way as the score, often enough that
  chance alone would rarely do it: an exact two-sided sign test over the tasks that got better or worse, at
  five in a hundred. Tasks that scored the same carry no direction and are left
  out of the test.

  A change that clears the rule but fails the test, or one that rises or falls
  by less than the rule asks, is too close to call. Two runs that scored
  exactly the same are no difference, and a Campaign that set no rule cannot
  decide.

  Both the Result pages and the read endpoints use this, so the two never
  disagree.
  """

  alias Techtree.Network.Assessment

  @type t :: :improved | :regressed | :too_close_to_call | :no_difference | :no_rule

  # The largest chance, out of one, that a run of tasks this one-sided could
  # come from a Skill that made no difference.
  @significance 0.05

  @doc """
  The verdict one Result's assessment comes to.
  """
  @spec of(Assessment.t()) :: t()
  def of(%Assessment{reason: :no_rule}), do: :no_rule
  def of(%Assessment{reason: :unchanged}), do: :no_difference

  def of(%Assessment{reason: :cleared_rule, wins: wins, losses: losses}),
    do: if(one_sided?(wins, losses), do: :improved, else: :too_close_to_call)

  def of(%Assessment{reason: :fell_past_rule, wins: wins, losses: losses}),
    do: if(one_sided?(losses, wins), do: :regressed, else: :too_close_to_call)

  def of(%Assessment{}), do: :too_close_to_call

  @doc """
  Whether more tasks went the first way than the second, often enough to rule
  out chance.
  """
  @spec one_sided?(non_neg_integer(), non_neg_integer()) :: boolean()
  def one_sided?(toward, against),
    do: toward > against and sign_test(toward, against) <= @significance

  # The exact two-sided sign test: the chance of a split at least this uneven
  # among the tasks that moved, if each was as likely to go either way.
  defp sign_test(0, 0), do: 1.0

  defp sign_test(wins, losses) do
    moved = wins + losses
    tail = Enum.sum(for k <- 0..min(wins, losses), do: choose(moved, k))
    min(1.0, 2 * tail / Integer.pow(2, moved))
  end

  defp choose(n, k), do: div(Enum.product((n - k + 1)..n//1), Enum.product(1..k//1))
end
