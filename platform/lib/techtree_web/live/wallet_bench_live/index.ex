defmodule TechtreeWeb.WalletBenchLive.Index do
  @moduledoc """
  Every wallet test attempt, newest first: the pair, its status, the install
  and wallet results, and what the tested model cost. Updates as attempts move.
  """

  use TechtreeWeb, :live_view

  alias Techtree.WalletBench
  alias TechtreeWeb.WalletBenchCopy, as: Copy

  @impl true
  def mount(_params, _session, socket) do
    if connected?(socket), do: TechtreeWeb.Endpoint.subscribe("wallet_bench:attempts")
    {:ok, socket |> assign(page_title: "Wallet tests") |> load()}
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
          <p class="wallet-bench__lede">
            A coding agent on a clean machine is asked to install a wallet tool from its official
            page, then to set up a wallet it controls and prove it with a signature. Every turn is
            recorded and judged. Newest first.
          </p>
        </header>

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
