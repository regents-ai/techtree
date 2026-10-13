defmodule TechtreeWeb.WalletBenchLive.Index do
  @moduledoc """
  Which agent works with which wallet, then every wallet test attempt, newest
  first: the pair, its status, the install and wallet results, and what the
  tested model cost. Attempts with no result stay hidden until "Show all".
  Updates as attempts move.
  """

  use TechtreeWeb, :live_view

  alias Techtree.WalletBench
  alias Techtree.WalletBench.Judge
  alias TechtreeWeb.WalletBenchCopy, as: Copy

  @impl true
  def mount(_params, _session, socket) do
    if connected?(socket), do: TechtreeWeb.Endpoint.subscribe("wallet_bench:attempts")
    {:ok, socket |> assign(page_title: "Wallet Bench", judge: Judge.model()) |> load()}
  end

  @impl true
  def handle_params(params, _uri, socket),
    do: {:noreply, socket |> assign(all?: Map.has_key?(params, "all")) |> listed()}

  @impl true
  def handle_info(%Phoenix.Socket.Broadcast{}, socket),
    do: {:noreply, socket |> load() |> listed()}

  defp load(socket) do
    attempts = WalletBench.list_attempts!(load: [:turns, :model_spend_usd])
    assign(socket, attempts: attempts, answer: Copy.answer(attempts))
  end

  defp listed(%{assigns: %{all?: true, attempts: attempts}} = socket),
    do: assign(socket, listed: attempts, hidden: 0)

  defp listed(%{assigns: %{attempts: attempts}} = socket) do
    listed = Enum.filter(attempts, &Copy.settled_or_running?/1)
    assign(socket, listed: listed, hidden: length(attempts) - length(listed))
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page wide>
      <div class="wallet-bench">
        <header class="page-heading wallet-bench__intro">
          <p class="eyebrow">AgentWalletBench</p>
          <h1>Wallet Bench</h1>
        </header>

        <section :if={@attempts != []} class="wallet-bench__answer" aria-labelledby="bench-answer">
          <h2 id="bench-answer">Which agent works with which wallet</h2>
          <p class="quiet">Each box is the pair's newest judged test.</p>
          <div
            class="wallet-bench__frame"
            role="region"
            aria-label="Agents and wallets, scroll horizontally for all wallets"
            tabindex="0"
          >
            <table class="results-ledger wallet-bench__grid">
              <thead>
                <tr>
                  <th scope="col">Agent</th>
                  <th :for={wallet <- @answer.wallets} scope="col">{wallet}</th>
                </tr>
              </thead>
              <tbody>
                <tr :for={row <- @answer.rows}>
                  <th scope="row">{row.agent}</th>
                  <td
                    :for={cell <- row.cells}
                    class={"wallet-bench__cell wallet-bench__cell--#{Copy.tone(cell && cell.ruling)}"}
                  >
                    <.link :if={cell} navigate={~p"/wallet-bench/#{cell.attempt.id}"}>
                      {Copy.verdict(cell.ruling)}
                    </.link>
                    <span :if={!cell} class="quiet">Not yet</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <details class="wallet-bench__how">
          <summary>How each test runs</summary>
          <ol class="wallet-bench__steps">
            <li>A clean machine starts with the coding agent installed and nothing else.</li>
            <li>The agent is asked to install a wallet tool from the tool's official page.</li>
            <li>
              It is then asked to set up a wallet it controls, say how the keys are kept, and
              prove control with a signature.
            </li>
            <li>Everything the agent does is recorded, with secrets blanked before it is stored.</li>
            <li>
              A judge model, {@judge}, rules on each of the agent's answers against nine checks,
              and the bench checks any wallet address and signature on Base itself.
            </li>
            <li>The machine goes back to its clean start for the next test.</li>
          </ol>
          <p>
            On 7 Oct 2026 the wallet question gained one sentence asking the agent to make a wallet
            if it had none. Tests sent the earlier wording are marked “(earlier question)”, and each
            test's page shows the prompt it was sent, word for word.
          </p>
        </details>

        <h2 :if={@attempts != []}>Every test</h2>

        <p :if={@attempts != []} class="wallet-bench__listing quiet">
          <span :if={@hidden > 0}>Newest first. Tests with no result are hidden.</span>
          <span :if={@hidden == 0}>Newest first.</span>
          <.link :if={!@all? and @hidden > 0} patch={~p"/wallet-bench?all"}>Show all</.link>
          <.link :if={@all?} patch={~p"/wallet-bench"}>Show fewer</.link>
        </p>

        <p :if={@attempts == []} class="quiet">No tests have run yet.</p>

        <div
          :if={@attempts != []}
          class="wallet-bench__frame"
          role="region"
          aria-label="Wallet tests, scroll horizontally for all columns"
          tabindex="0"
        >
          <table class="results-ledger">
            <thead>
              <tr>
                <th scope="col">Agent and wallet</th>
                <th scope="col">Started</th>
                <th scope="col">Status</th>
                <th scope="col">Install</th>
                <th scope="col">Wallet</th>
                <th scope="col" class="results-ledger__numeric">Model cost</th>
              </tr>
            </thead>
            <tbody>
              <tr :for={attempt <- @listed} id={"attempt-#{attempt.id}"}>
                <th scope="row">
                  <.link navigate={~p"/wallet-bench/#{attempt.id}"}>{Copy.pair(attempt)}</.link>
                </th>
                <td class="results-ledger__date">
                  {Calendar.strftime(attempt.inserted_at, "%d %b %Y %H:%M")} UTC
                </td>
                <td>{Copy.status(attempt.state)}</td>
                <td>{attempt.turns |> Copy.install_result() |> Copy.outcome()}</td>
                <td>
                  {attempt.turns |> Copy.wallet_result() |> Copy.outcome()}
                  <span :if={Copy.earlier_question?(attempt)} class="quiet">(earlier question)</span>
                </td>
                <td class="results-ledger__numeric">{Copy.dollars(attempt.model_spend_usd)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </Layouts.page>
    """
  end
end
