defmodule TechtreeWeb.PointsEntries do
  @moduledoc """
  How the Points page and the agent's Points answer describe one account's
  Points summary (`RegentPoints.summary/1`), so both say the same thing about
  each entry and allowance.
  """

  alias RegentPoints.Amount

  @doc "What became of an entry: counted, cut to nothing by an allowance, or a correction."
  def status(%{reversal_of_entry_id: id}) when not is_nil(id), do: :correction
  def status(%{points_micro_delta: 0}), do: :allowance_reached
  def status(_entry), do: :counted

  def status_label(:counted), do: "Counted"
  def status_label(:allowance_reached), do: "Allowance reached"
  def status_label(:correction), do: "Correction"

  @doc "Who earned an entry, by the name the person gave their agent."
  def agent_name(%{actor_kind: "agent", actor_id: id}, names),
    do: Map.get(names, id, "Previously connected agent")

  def agent_name(_entry, _names), do: nil

  def allowance_name("activity:account"), do: "You and your agents"
  def allowance_name("credits"), do: "Credits purchases"

  @doc "The agent's Points answer: the same figures the Points page shows."
  def answer(summary) do
    %{
      points: Amount.format(summary.balance_micro),
      earned_today: Amount.format(summary.earned_today_micro),
      activity_being_verified: summary.pending,
      daily_allowances:
        Enum.map(
          summary.allowances,
          &%{name: allowance_name(&1.scope), remaining: Amount.format(&1.remaining)}
        ),
      entries:
        Enum.map(summary.entries, fn entry ->
          %{
            label: RegentPoints.Rules.label(entry.rule_id),
            points: Amount.format(entry.points_micro_delta),
            status: status(entry),
            allowance_reduction: Amount.format(entry.cap_reduction_micro),
            by: if(entry.actor_kind == "agent", do: "agent", else: "person"),
            agent: agent_name(entry, summary.agent_names),
            earned_at: entry.earned_at
          }
        end),
      period_bonuses:
        Enum.map(
          summary.period_bonuses,
          &%{
            period: &1.period,
            points: Amount.format(&1.bonus_micro),
            nft_count: &1.nft_count,
            bonus_percent: &1.bonus_percent
          }
        ),
      more: summary.more?
    }
  end
end
