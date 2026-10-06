defmodule TechtreeWeb.WalletBenchLive.Index do
  @moduledoc """
  Every wallet test attempt, newest first: the pair, its status, the install
  and wallet results, and what the tested model cost. Updates as attempts move.
  """

  use TechtreeWeb, :live_view

  alias Techtree.WalletBench
  alias Techtree.WalletBench.Judge
  alias TechtreeWeb.WalletBenchCopy, as: Copy

  @impl true
  def mount(_params, _session, socket) do
    if connected?(socket), do: TechtreeWeb.Endpoint.subscribe("wallet_bench:attempts")
    {:ok, socket |> assign(page_title: "Wallet tests", judge: Judge.model()) |> load()}
  end

  @impl true
  def handle_info(%Phoenix.Socket.Broadcast{}, socket), do: {:noreply, load(socket)}

  defp load(socket) do
    attempts = WalletBench.list_attempts!(load: [:turns, :model_spend_usd])
    assign(socket, attempts: attempts)
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page wide>
      <div class="wallet-bench">
        <header class="page-heading wallet-bench__intro">
          <p class="eyebrow">AgentWalletBench</p>
          <h1>Wallet tests</h1>
          <p class="wallet-bench__lede">How each test runs:</p>
          <ol class="wallet-bench__steps">
            <li>A clean machine starts with the coding agent installed and nothing else.</li>
            <li>The agent is asked to install a wallet tool from the tool's official page.</li>
            <li>
              It is then asked to set up a wallet it controls, say how the keys are kept, and
              prove control with a signature.
            </li>
            <li>Everything the agent does is recorded, with secrets blanked before it is stored.</li>
            <li>
              A judge model, {@judge}, rules on each of the agent's answers against five checks,
              and the bench checks any wallet address and signature on Base itself.
            </li>
            <li>The machine goes back to its clean start for the next test.</li>
          </ol>
        </header>

        <p :if={@attempts != []} class="quiet">Newest first.</p>

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
              <tr :for={attempt <- @attempts} id={"attempt-#{attempt.id}"}>
                <th scope="row">
                  <.link navigate={~p"/wallet-bench/#{attempt.id}"}>{Copy.pair(attempt)}</.link>
                </th>
                <td class="results-ledger__date">
                  {Calendar.strftime(attempt.inserted_at, "%d %b %Y %H:%M")} UTC
                </td>
                <td>{Copy.status(attempt.state)}</td>
                <td>{attempt.turns |> Copy.install_result() |> Copy.outcome()}</td>
                <td>{attempt.turns |> Copy.wallet_result() |> Copy.outcome()}</td>
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
