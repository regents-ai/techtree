defmodule TechtreeWeb.PointsEntries do
  @moduledoc """
  How the Points page and the agent's Points answer describe one account's
  Points (`RegentPoints.summary/1` and the board every reader shares,
  `Techtree.Points.Board`), so both say the same thing about each action,
  entry and place.
  """

  alias RegentPoints.{Amount, Rules}

  @doc "What became of an entry: counted, cut to nothing by a daily limit, or a correction."
  def status(%{reversal_of_entry_id: id}) when not is_nil(id), do: :correction
  def status(%{points_micro_delta: 0}), do: :allowance_reached
  def status(_entry), do: :counted

  def status_label(:counted), do: "Counted"
  def status_label(:allowance_reached), do: "Limit reached"
  def status_label(:correction), do: "Correction"

  @doc "Who earned an entry, by the name the person gave their agent."
  def agent_name(%{actor_kind: "agent", actor_id: id}, names),
    do: Map.get(names, id, "Previously connected agent")

  def agent_name(_entry, _names), do: nil

  @doc """
  The actions this site lists, in two groups, with what the account has done of
  each: `[%{title, limit, items}]`. `open?` is false until earning opens; an
  action then carries no points and nothing is done or left.
  """
  def todo(summary, open?) do
    rules = Rules.tracked()
    room = Map.new(summary.allowances, &{&1.scope, &1})

    [
      %{
        title: "Once",
        limit: nil,
        items: for(%{"category" => "milestone"} = rule <- rules, do: once(rule, summary, open?))
      },
      %{
        title: "Daily",
        limit: limit(room["activity:account"]),
        items:
          for(%{"category" => "activity"} = rule <- rules, do: daily(rule, summary, room, open?))
      }
    ]
  end

  @doc "How many listed actions can still earn: today for a daily one."
  def left(groups), do: groups |> Enum.flat_map(& &1.items) |> Enum.count(& &1.left)

  @doc """
  The shared board for one reader: `%{rows, you, rank}`. `reader` is the reader's
  account id and `summary` their own summary (`RegentPoints.summary/1`), or `nil`
  while it is not read. `you` is the reader's row when they sit below the listed
  rows; `rank` is their place wherever they sit, the summary's `place`. The rows'
  account ids stay here: they never reach a page or an agent. A row's `name` is
  `nil` when the person shows by their `wallet`, under its `ens_name` when it has
  one. A row's `line` is its position in the list: names and places repeat, lines
  do not.
  """
  def board(%{top: top}, reader, summary) do
    rank = summary && summary.place
    listed? = Enum.any?(top, &(&1.account_id == reader))

    %{
      rows:
        top
        |> Enum.with_index(1)
        |> Enum.map(fn {row, line} ->
          %{
            line: line,
            rank: row.rank,
            name: row.name,
            wallet: row.wallet,
            ens_name: row.ens_name,
            squares: row.squares,
            picture: row.picture,
            points: Amount.format(row.points_micro),
            you: row.account_id == reader
          }
        end),
      you: if(rank && !listed?, do: %{rank: rank, points: Amount.format(summary.balance_micro)}),
      rank: rank
    }
  end

  @doc "The agent's Points answer: the same figures the Points page shows."
  def answer(summary, board, reader, open?) do
    board = board(board, reader, summary)

    %{
      points: Amount.format(summary.balance_micro),
      earned_today: Amount.format(summary.earned_today_micro),
      earned_yesterday: Amount.format(summary.earned_yesterday_micro),
      rank: board.rank,
      activity_being_verified: summary.pending,
      to_do:
        for group <- todo(summary, open?), item <- group.items do
          %{
            label: item.label,
            repeats: String.downcase(group.title),
            points: item.points,
            done: item.done,
            left: item.left,
            today: item[:count]
          }
        end,
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
        Enum.map(board.rows, &Map.take(&1, [:rank, :name, :wallet, :ens_name, :points, :you])),
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

  defp limit_name("activity:account"), do: "Daily actions, you and your agents"

  defp once(%{"id" => id, "points" => points}, summary, open?) do
    done = open? and Map.fetch!(summary.done, id) >= 1

    %{
      id: id,
      label: Rules.label(id),
      points: open? && to_string(points),
      done: done,
      left: open? and not done
    }
  end

  defp daily(%{"id" => id, "points" => points, "count" => of}, summary, room, open?)
       when is_integer(of) do
    item = %{
      id: id,
      label: Rules.label(id),
      points: open? && to_string(points),
      done: false,
      left: false
    }

    case room["activity:account"] do
      %{remaining: remaining} ->
        done = Map.fetch!(summary.done, id)

        item
        |> Map.merge(%{
          note: "#{done} of #{of} today",
          done: done >= of,
          left: done < of and remaining > 0
        })
        |> then(&if of > 1, do: Map.put(&1, :count, %{done: done, of: of}), else: &1)

      nil ->
        item
    end
  end

  # The one limit every daily action shares, whoever acted.
  defp limit(nil), do: nil

  defp limit(%{limit: limit, remaining: remaining}) do
    used = whole(limit - remaining)
    %{label: "Limit", used: used, of: whole(limit), value: "#{used} of #{whole(limit)} today"}
  end

  defp whole(micro), do: div(micro, Rules.unit())
end
