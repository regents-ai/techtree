defmodule TechtreeWeb.WalletBenchLive.Show do
  @moduledoc """
  One wallet test attempt: the machine it ran on, the extra notes on its
  agent's and wallet tool's versions, each test's ruling with its
  checks and reasons, the bench's own checks, the funding sends of a money
  attempt, the stored evidence and everything that happened, in order.
  Updates as the attempt moves.
  """

  use TechtreeWeb, :live_view

  alias Techtree.WalletBench
  alias Techtree.WalletBench.Catalog
  alias TechtreeWeb.WalletBenchCopy, as: Copy

  import TechtreeWeb.WalletBenchLive.Turn, only: [turn: 1]
  alias TechtreeWeb.WalletBenchLive.Turn

  @load [:machine, :turns, :payments, :model_spend_usd, :judge_cost_usd]

  @impl true
  def mount(%{"id" => id}, _session, socket) do
    with {:ok, id} <- Ecto.UUID.cast(id),
         {:ok, attempt} <- WalletBench.get_attempt(id, load: @load) do
      if connected?(socket) do
        TechtreeWeb.Endpoint.subscribe("wallet_bench:attempts")
        TechtreeWeb.Endpoint.subscribe("wallet_bench:attempts:#{id}")
      end

      {:ok, show(socket, attempt)}
    else
      _missing -> raise TechtreeWeb.NotFoundError, "no wallet test has that number"
    end
  end

  @impl true
  def handle_info(%Phoenix.Socket.Broadcast{}, socket) do
    {:noreply, show(socket, WalletBench.get_attempt!(socket.assigns.attempt.id, load: @load))}
  end

  defp show(socket, attempt) do
    assign(socket,
      page_title: Copy.pair(attempt),
      attempt: attempt,
      judges: judges(attempt),
      notes: notes(attempt),
      events: WalletBench.list_attempt_events!(attempt.id)
    )
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page wide>
      <article class="wallet-bench">
        <header class="page-heading wallet-bench__intro">
          <p class="back-link"><.link navigate={~p"/wallet-bench"}>← Wallet tests</.link></p>
          <h1>{Copy.pair(@attempt)}</h1>
          <p class="wallet-bench__lede">
            {Copy.status(@attempt.state)}. Started {Calendar.strftime(
              @attempt.inserted_at,
              "%d %b %Y %H:%M"
            )} UTC.
          </p>
          <p :if={@attempt.failure} class="wallet-bench__failure">{@attempt.failure}</p>
          <p :if={@attempt.funding_refused}>Not funded: {@attempt.funding_refused}</p>
        </header>

        <section class="wallet-bench__section" aria-labelledby="setup">
          <h2 id="setup">Setup</h2>
          <dl :if={@attempt.machine} class="wallet-bench__facts">
            <dt>Agent</dt>
            <dd>{@attempt.machine.manifest["harness_version"]}</dd>
            <dt>Model</dt>
            <dd>
              {@attempt.machine.manifest["model"]}, {@attempt.machine.manifest["reasoning_effort"]} effort
            </dd>
            <dt>Machine</dt>
            <dd>{@attempt.machine.manifest["os"]}</dd>
            <dt>Tests</dt>
            <dd>
              {if @attempt.plan == :money,
                do:
                  "Install and wallet, then, once funded, the refund, the paid call and the Patchbay sign-in",
                else: "Install and wallet"}
            </dd>
            <dt>Wallet tool</dt>
            <dd>{wallet(@attempt).name}, run as <code>{wallet(@attempt).executable}</code></dd>
            <dt>Version the survey installed</dt>
            <dd>{wallet(@attempt).survey_version}</dd>
            <dt :if={@judges != []}>Judge</dt>
            <dd :if={@judges != []}>{Enum.join(@judges, ", ")}</dd>
          </dl>
          <p :if={!@attempt.machine} class="quiet">No machine yet.</p>
          <div :if={@notes != []} id="extra-notes">
            <h3>Extra notes for these versions</h3>
            <ul>
              <li :for={note <- @notes}>{Copy.subject(note)} {note.version}: {note.text}</li>
            </ul>
          </div>
        </section>

        <.turn :for={turn <- @attempt.turns} attempt_id={@attempt.id} turn={turn} />

        <section
          :if={@attempt.payments != []}
          class="wallet-bench__section"
          aria-labelledby="funding"
        >
          <h2 id="funding">Funding</h2>
          <p>
            Sent to {@attempt.agent_address} on Base from the bench's wallet {hd(@attempt.payments).from}.
          </p>
          <table class="results-ledger">
            <thead>
              <tr>
                <th scope="col">Sent</th>
                <th scope="col">State</th>
                <th scope="col">Transaction</th>
              </tr>
            </thead>
            <tbody>
              <tr :for={payment <- @attempt.payments}>
                <td>{Copy.payment(payment)}</td>
                <td>{Copy.payment_state(payment.state)}</td>
                <td><a href={"https://basescan.org/tx/" <> payment.hash}>{payment.hash}</a></td>
              </tr>
            </tbody>
          </table>
        </section>

        <section class="wallet-bench__section" aria-labelledby="totals">
          <h2 id="totals">Totals</h2>
          <dl class="wallet-bench__facts">
            <dt>Model cost</dt>
            <dd>{Copy.dollars(@attempt.model_spend_usd)}</dd>
            <dt>Judge cost</dt>
            <dd>{Copy.dollars(@attempt.judge_cost_usd)}</dd>
          </dl>
        </section>

        <section class="wallet-bench__section" aria-labelledby="history">
          <h2 id="history">What happened</h2>
          <ol class="wallet-bench__events">
            <li :for={event <- @events}>
              <time datetime={DateTime.to_iso8601(event.inserted_at)}>
                {Calendar.strftime(event.inserted_at, "%H:%M:%S")}
              </time>
              {Copy.step(event.step)}
              <span :if={event.detail["failure"]} class="wallet-bench__failure">{event.detail[
                "failure"
              ]}</span>
            </li>
          </ol>
        </section>
      </article>
    </Layouts.page>
    """
  end

  defp wallet(attempt), do: Catalog.wallet!(attempt.wallet_id)

  # The notes on the two releases this attempt used, as the bench's results name them: the agent's from the
  # machine's manifest, the wallet tool's from the newest install check, without a leading "v".
  defp notes(attempt) do
    WalletBench.list_run_version_notes!(
      attempt.harness_id,
      attempt.machine && attempt.machine.manifest["harness_version"],
      attempt.wallet_id,
      wallet_version(attempt)
    )
  end

  defp wallet_version(attempt) do
    attempt.turns
    |> Enum.reverse()
    |> Enum.find_value(&(&1.test in [:T1a, :T1b] && &1.checks["version"]["installed"]))
    |> case do
      "v" <> version -> version
      version -> version
    end
  end

  # The models that ruled on this attempt's turns, as each ruling recorded.
  defp judges(attempt) do
    attempt.turns
    |> Enum.filter(&Turn.scored?/1)
    |> Enum.map(& &1.judgment["model"])
    |> Enum.uniq()
  end
end
