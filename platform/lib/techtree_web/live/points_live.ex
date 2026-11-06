defmodule TechtreeWeb.PointsLive do
  @moduledoc """
  Private Account Points presentation: the total, the actions left, the
  leaderboard, the NFT bonus added at the end of each 30-day period, and the
  activity. The pieces are `Regent.Points`; this page supplies their words.
  """
  use TechtreeWeb, :html
  import TechtreeWeb.Components.AccountControls, only: [account_picture: 1]
  import TechtreeWeb.Components.PageHead, only: [page_head: 1]
  alias RegentPoints.{Amount, Rules}
  alias TechtreeWeb.PointsEntries

  attr :account, :map, default: nil
  attr :signed_out_reason, :atom, default: :signed_out
  attr :points, TechtreeWeb.Read, required: true

  attr :board, TechtreeWeb.Read,
    required: true,
    doc: "the board every signed-in reader shares (Techtree.Points.Board)"

  attr :bonus, TechtreeWeb.Read,
    required: true,
    doc: "the NFT tier the account's wallets hold now"

  attr :earning, :list, required: true, doc: "the catalog rules earning now"

  def page(assigns) do
    open? = assigns.earning != []
    summary = assigns.points.value
    groups = if summary, do: PointsEntries.todo(summary, open?), else: []

    board =
      assigns.board.value &&
        PointsEntries.board(
          assigns.board.value,
          assigns.account.id,
          summary && summary.balance_micro
        )

    assigns =
      assign(assigns,
        open?: open?,
        summary: summary,
        groups: Enum.map(groups, &linked/1),
        left: if(summary && open?, do: PointsEntries.left(groups)),
        places: board,
        rows: if(summary, do: Enum.map(summary.entries, &row(&1, summary.agent_names)), else: [])
      )

    ~H"""
    <article id="points-page" class="account-page">
      <.page_head title="Points" />
      <Regent.Account.signed_out
        :if={is_nil(@account)}
        id="points-signed-out"
        reason={@signed_out_reason}
      >
        <:sign_in>
          <Regent.Primitives.button type="button" data-account-target="sign-in">
            Sign in
          </Regent.Primitives.button>
        </:sign_in>
      </Regent.Account.signed_out>
      <Regent.Points.layout :if={@account}>
        <:total>
          <Regent.Points.total
            id="points-total"
            total={@summary && Amount.format(@summary.balance_micro)}
            today={@summary && Amount.format(@summary.earned_today_micro)}
            yesterday={@summary && Amount.format(@summary.earned_yesterday_micro)}
            rank={@places && @places.rank && to_string(@places.rank)}
            pending={if @summary, do: @summary.pending, else: 0}
            state={state(@points)}
          >
            A record of everything you and your agents do across Regents. One total, on every site.
          </Regent.Points.total>
        </:total>
        <:main>
          <Regent.Points.todo :if={@summary} id="points-todo" left={@left} groups={@groups}>
            <p :if={!@open?} role="status">Earning hasn’t opened yet.</p>
          </Regent.Points.todo>
          <Regent.Points.activity
            :if={@summary}
            id="points-activity"
            rows={@rows}
            more={@summary.more?}
          >
            <:tip :let={row}>
              <Regent.Primitives.tip id={"points-limit-#{row.id}"} label="About this award’s limit">
                {row.note}
              </Regent.Primitives.tip>
            </:tip>
          </Regent.Points.activity>
        </:main>
        <:side>
          <Regent.Points.board
            id="points-board"
            rows={if @places, do: @places.rows, else: []}
            you={@places && @places.you}
            state={state(@board)}
          >
            <:face :let={row}>
              <.account_picture
                id={"points-board-face-#{row.line}"}
                squares={row.squares}
                picture={row.picture}
                size={28}
              />
            </:face>
          </Regent.Points.board>
          <Regent.Points.bonus
            id="points-bonus"
            state={bonus_state(@open?, @bonus)}
            nfts={@bonus.value && @bonus.value.nft_count}
            percent={@bonus.value && @bonus.value.percent}
            message={"Your NFTs could not be checked. #{retry(@bonus.error)}"}
            tiers={tiers(@bonus.value)}
            periods={if @summary, do: periods(@summary), else: []}
          >
            <:tip>
              <Regent.Primitives.tip id="points-bonus-about" label="About your points bonus">
                Animata I, Animata II and Regents Club count across your verified linked wallets.
                At the end of each 30-day period, the tier your wallets hold that day adds its
                bonus to the points you earned in that period, one-time awards included.
              </Regent.Primitives.tip>
            </:tip>
          </Regent.Points.bonus>
        </:side>
      </Regent.Points.layout>
    </article>
    """
  end

  # The page where each action is done, for the ones this site has a page for.
  @links %{
    "social.x" => "/account/connections",
    "social.github" => "/account/connections",
    "social.farcaster" => "/account/connections",
    "agent.activated" => "/account/agents"
  }

  defp linked(group) do
    items =
      Enum.map(group.items, fn item ->
        item
        |> Map.put(:points, item.points && "+" <> item.points)
        |> then(&if href = @links[item.id], do: Map.put(&1, :href, href), else: &1)
      end)

    %{group | items: items}
  end

  defp row(entry, agent_names) do
    status = PointsEntries.status(entry)

    %{
      id: entry.id,
      label: Rules.label(entry.rule_id),
      by: PointsEntries.agent_name(entry, agent_names) || "You",
      at: Calendar.strftime(entry.earned_at, "%-d %b, %H:%M UTC"),
      points: signed(entry.points_micro_delta),
      status: if(status != :counted, do: PointsEntries.status_label(status)),
      note: if(entry.cap_reduction_micro > 0, do: cut(entry))
    }
  end

  defp cut(entry) do
    "#{Amount.format(entry.points_micro_delta + entry.cap_reduction_micro)} before limits, " <>
      "#{Amount.format(entry.points_micro_delta)} awarded. The rest was over the daily limit."
  end

  defp signed(micro) when micro < 0, do: "−" <> Amount.format(-micro)
  defp signed(micro), do: "+" <> Amount.format(micro)

  # The period running now, then the bonuses already added, newest first.
  defp periods(summary) do
    current =
      case summary.current_period do
        %{number: number, ends_at: ends_at, earned_micro: earned} ->
          [
            %{
              label: "Period #{number}",
              value:
                "#{Amount.format(earned)} earned, ends #{Calendar.strftime(ends_at, "%-d %b")}"
            }
          ]

        nil ->
          []
      end

    current ++
      Enum.map(summary.period_bonuses, fn period ->
        %{
          label: "Period #{period.period}",
          value:
            "+#{Amount.format(period.bonus_micro)} (#{period.nft_count} NFTs, +#{period.bonus_percent}%)"
        }
      end)
  end

  # Ascending tiers, each running up to the next one's minimum.
  defp tiers(held) do
    ascending = Enum.sort(RegentPoints.Bonus.tiers())
    next = Enum.map(Enum.drop(ascending, 1), &elem(&1, 0)) ++ [nil]
    count = held && held.nft_count

    Enum.zip_with(ascending, next, fn
      {minimum, percent}, nil ->
        %{range: "#{minimum}+", percent: percent, held: is_integer(count) and count >= minimum}

      {minimum, percent}, upper ->
        %{
          range: "#{minimum}–#{upper - 1}",
          percent: percent,
          held: is_integer(count) and count in minimum..(upper - 1)
        }
    end)
  end

  defp state(%{state: state}) when state in [:idle, :loading], do: :loading
  defp state(%{state: state}) when state in [:ready, :empty], do: :ready
  defp state(%{state: state}), do: state

  defp bonus_state(false, _bonus), do: :closed
  defp bonus_state(true, bonus), do: state(bonus)

  # Reading again at once while limited would only be refused again.
  defp retry(:limited), do: "Try again in a minute."
  defp retry(_reason), do: "Try refreshing this page."
end
