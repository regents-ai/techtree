defmodule TechtreeWeb.CreditsHistoryLive do
  @moduledoc """
  A person's own Credits history: purchases, gifts, Credits set aside, spent
  and returned on each Regent site, and refunds, newest first, each with its
  date and time. The entries and their words come from Regent Credits
  (`RegentCredits.History`, `RegentCredits.History.Words`), so every site
  shows the same thing the same way. A purchase's View opens its payment on
  its chain's explorer. Buy Credits opens the header's own Buy
  Credits panel. What Credits buy lists each place to spend them, for everyone:
  the other Regent sites' uses. Techtree has no use of its own yet: benchmark
  charging is not enabled.
  """
  use TechtreeWeb, :html
  import TechtreeWeb.Components.PageHead, only: [page_head: 1]
  alias RegentCredits.{Amount, History.Words}

  @uses [
    %{
      site: "Patchbay",
      words: "Bid for an Agent Offer",
      url: "https://patchbay.help/offers/how-it-works"
    }
  ]

  @explorers %{
    base: %{name: "Basescan", tx: "https://basescan.org/tx/"},
    ethereum: %{name: "Etherscan", tx: "https://etherscan.io/tx/"}
  }

  attr :account, :map, default: nil
  attr :signed_out_reason, :atom, default: :signed_out

  attr :history, TechtreeWeb.Read,
    required: true,
    doc: "the entries read so far, with `more?` and `next` for older ones"

  def page(assigns) do
    assigns = assign(assigns, :uses, @uses)

    ~H"""
    <article id="credits-history-page" class="account-page">
      <.page_head title="Credits history">
        <:tip>Everything that changed your Credits, on every Regent site.</:tip>
        <:actions :if={@account}>
          <Regent.Primitives.button
            id="credits-history-buy"
            type="button"
            aria-haspopup="dialog"
            aria-controls="shell-credits"
            data-credits-open
          >
            Buy Credits
          </Regent.Primitives.button>
        </:actions>
      </.page_head>
      <Regent.Account.signed_out
        :if={is_nil(@account)}
        id="credits-history-signed-out"
        reason={@signed_out_reason}
      >
        <:sign_in>
          <Regent.Primitives.button type="button" data-account-target="sign-in">
            Sign in
          </Regent.Primitives.button>
        </:sign_in>
      </Regent.Account.signed_out>
      <div :if={@account} class="account-grid">
        <.entries
          id="credits-history"
          title="Your Credits"
          history={@history}
          empty_message="Nothing has changed your Credits yet."
        />
      </div>
      <section id="credits-uses" class="account-panel credits-uses">
        <h2>What Credits buy</h2>
        <ul>
          <li :for={use <- @uses}>
            <span class="account-kicker">{use.site}</span>
            <a href={use.url}>{use.words}</a>
          </li>
        </ul>
      </section>
    </article>
    """
  end

  attr :id, :string, required: true
  attr :title, :string, required: true
  attr :history, TechtreeWeb.Read, required: true
  attr :empty_message, :string, required: true

  attr :message, :string,
    default: nil,
    doc: "what to say instead of the usual words for the read's state"

  attr :target, :any, default: nil, doc: "the component that reads older entries, if not the page"

  @doc "The entries with a button for older ones; the admin page shows a person's the same way."
  def entries(assigns) do
    ~H"""
    <div class="credits-history">
      <Regent.Account.history
        id={@id}
        title={@title}
        rows={rows(@history.value)}
        empty_message={@empty_message}
        state={state(@history)}
        message={@message}
      />
      <Regent.Primitives.button
        :if={@history.value && @history.value.more?}
        id={"#{@id}-older"}
        type="button"
        variant="secondary"
        phx-click="credits_history_older"
        phx-target={@target}
      >
        Show older
      </Regent.Primitives.button>
    </div>
    """
  end

  defp rows(nil), do: []
  defp rows(%{entries: entries}), do: Enum.map(entries, &row/1)

  defp row(entry) do
    entry
    |> payment()
    |> Map.merge(%{
      label: Words.line(entry),
      amount: signed(entry.direction) <> Amount.format(entry.amount),
      occurred_at: Calendar.strftime(entry.at, "%d %b %Y %H:%M UTC")
    })
  end

  # Credits bought before sign-in, or a purchase whose row is gone, carry no
  # payment, so their rows have no link.
  defp payment(%{kind: :bought, chain: chain, tx_hash: tx_hash})
       when is_map_key(@explorers, chain) and is_binary(tx_hash) do
    %{
      link: %{
        href: transaction_url(chain, tx_hash),
        label: "View",
        description: "View this transaction on #{@explorers[chain].name}"
      }
    }
  end

  defp payment(_entry), do: %{}

  @doc """
  A payment's page on its chain's explorer: the explorer's address and the
  transaction hash, which the purchase table holds only as `0x` and 64
  lowercase hex characters.
  """
  def transaction_url(chain, tx_hash), do: @explorers[chain].tx <> tx_hash

  defp signed(:in), do: "+"
  defp signed(:out), do: "−"
  defp signed(:none), do: ""

  @doc """
  Reads the page after `history`'s last one with `read`, a one-argument
  function given `%{after: next}`, and returns all the entries so far.
  """
  def older(history, read) do
    with {:ok, page} <- read.(%{after: history.next}),
         do: {:ok, %{page | entries: history.entries ++ page.entries}}
  end

  # Only a first read shows as loading; entries on screen stay while older ones
  # or a fresh first page are read.
  defp state(%{value: nil, state: state}) when state in [:idle, :loading], do: :loading
  defp state(%{state: state}) when state in [:loading, :empty], do: :ready
  defp state(%{state: state}), do: state
end
