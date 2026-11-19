defmodule TechtreeWeb.PointsEntries do
  @moduledoc """
  The paired agent's answer about its person's Points
  (`TechtreeWeb.AgentAccountController`): their own summary
  (`RegentPoints.summary/1`) and the board every reader shares
  (`Techtree.Points.Board`), with each action, entry and place described.
  """

  alias RegentPoints.{Amount, Rules}

  @doc """
  The agent's Points answer. `reader` is the person's account id; the board's
  account ids stay here and only mark the person's own row. `open?` is false
  until earning opens: an action then carries no points and nothing is done or
  left.
  """
  def answer(summary, %{top: top}, reader, open?) do
    %{
      points: Amount.format(summary.balance_micro),
      earned_today: Amount.format(summary.earned_today_micro),
      earned_yesterday: Amount.format(summary.earned_yesterday_micro),
      rank: summary.place,
      activity_being_verified: summary.pending,
      to_do: to_do(summary, open?),
      daily_limits:
        Enum.map(
          summary.allowances,
          &%{
            name: limit_name(&1.scope),
            limit: Amount.format(&1.limit),
            remaining: Amount.format(&1.remaining)
          }
        ),
      leaderboard:
        Enum.map(
          top,
          &%{
            rank: &1.rank,
            name: &1.name,
            wallet: &1.wallet,
            ens_name: &1.ens_name,
            points: Amount.format(&1.points_micro),
            you: &1.account_id == reader
          }
        ),
      entries:
        Enum.map(summary.entries, fn entry ->
          %{
            label: Rules.label(entry.rule_id),
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

  # The actions this site lists, the one-time ones first, with what the account
  # has done of each.
  defp to_do(summary, open?) do
    rules = Rules.tracked()
    room = Enum.find(summary.allowances, &(&1.scope == "activity:account"))

    for(%{"category" => "milestone"} = rule <- rules, do: once(rule, summary, open?)) ++
      for %{"category" => "activity"} = rule <- rules, do: daily(rule, summary, room, open?)
  end

  defp once(%{"id" => id, "points" => points}, summary, open?) do
    done = open? and Map.fetch!(summary.done, id).times >= 1

    %{
      label: Rules.label(id),
      repeats: "once",
      points: open? && to_string(points),
      done: done,
      left: open? and not done,
      today: nil
    }
  end

  defp daily(%{"id" => id, "points" => points, "count" => of}, summary, room, open?)
       when is_integer(of) do
    item = %{
      label: Rules.label(id),
      repeats: "daily",
      points: open? && to_string(points),
      done: false,
      left: false,
      today: nil
    }

    case room do
      %{remaining: remaining} ->
        done = Map.fetch!(summary.done, id).times

        %{
          item
          | done: done >= of,
            left: done < of and remaining > 0,
            today: if(of > 1, do: %{done: done, of: of})
        }

      nil ->
        item
    end
  end

  # What became of an entry: counted, cut to nothing by a daily limit, or a correction.
  defp status(%{reversal_of_entry_id: id}) when not is_nil(id), do: :correction
  defp status(%{points_micro_delta: 0}), do: :allowance_reached
  defp status(_entry), do: :counted

  # Who earned an entry, by the name the person gave their agent.
  defp agent_name(%{actor_kind: "agent", actor_id: id}, names),
    do: Map.get(names, id, "Previously connected agent")

  defp agent_name(_entry, _names), do: nil

  defp limit_name("activity:account"), do: "Daily actions, you and your agents"
end
