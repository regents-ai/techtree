defmodule TechtreeWeb.WalletBenchLive.Show do
  @moduledoc """
  One wallet test attempt: the machine it ran on, each test's ruling with its
  five checks and reasons, the bench's own checks, the stored evidence and
  everything that happened, in order. Updates as the attempt moves.
  """

  use TechtreeWeb, :live_view

  alias Techtree.WalletBench
  alias Techtree.WalletBench.Catalog
  alias TechtreeWeb.WalletBenchCopy, as: Copy

  @load [:machine, :turns, :model_spend_usd, :judge_cost_usd]

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
            <dt>Wallet tool</dt>
            <dd>{wallet(@attempt).name}, run as <code>{wallet(@attempt).executable}</code></dd>
            <dt>Version the survey installed</dt>
            <dd>{wallet(@attempt).survey_version}</dd>
            <dt :if={@judges != []}>Judge</dt>
            <dd :if={@judges != []}>{Enum.join(@judges, ", ")}</dd>
          </dl>
          <p :if={!@attempt.machine} class="quiet">No machine yet.</p>
        </section>

        <section
          :for={turn <- @attempt.turns}
          id={"test-#{Catalog.turn_name(turn.test)}"}
          class={["wallet-bench__test", "wallet-bench__test--#{Copy.tone(turn.judgment)}"]}
          aria-labelledby={"test-#{Catalog.turn_name(turn.test)}-title"}
        >
          <h2 id={"test-#{Catalog.turn_name(turn.test)}-title"}>{Copy.test(turn.test)}</h2>
          <p class="wallet-bench__outcome">
            <strong>{if turn.judgment,
              do: Copy.outcome(turn.judgment),
              else: Copy.turn_state(turn.state)}</strong>
          </p>
          <p :if={turn.failure} class="wallet-bench__failure">{turn.failure}</p>

          <%= if turn.judgment do %>
            <p>{turn.judgment["summary"]}</p>

            <table class="results-ledger wallet-bench__criteria">
              <caption class="sr-only">The judge's five checks</caption>
              <thead>
                <tr>
                  <th scope="col">Check</th>
                  <th scope="col">Answer</th>
                  <th scope="col">Why</th>
                </tr>
              </thead>
              <tbody>
                <tr :for={key <- ~w(C1 C2 C3 C4 C5)}>
                  <th scope="row">{Copy.criterion_question(turn.test, key)}</th>
                  <td class="wallet-bench__value">
                    {Copy.criterion(turn.judgment["criteria"][key]["value"])}
                  </td>
                  <td>{turn.judgment["criteria"][key]["reason"]}</td>
                </tr>
              </tbody>
            </table>

            <details class="wallet-bench__reasoning">
              <summary>The judge's reasoning</summary>
              <p>{turn.judgment["reasoning"]}</p>
            </details>
          <% end %>

          <dl class="wallet-bench__facts">
            <%= if turn.test == :T2 do %>
              <dt>Question asked</dt>
              <dd>
                {if Copy.current_question?(@attempt, turn),
                  do: "The current wording",
                  else: "The earlier wording, which did not ask the agent to make a wallet"}
              </dd>
            <% end %>
            <%= if version = turn.checks["version"] do %>
              <dt>Version installed</dt>
              <dd>
                {if version["installed"] == "", do: "Not shown", else: version["installed"]}{version_note(
                  version
                )}
              </dd>
            <% end %>
            <%= if base = Copy.base(turn.checks["base"]) do %>
              <dt>The bench's Base check</dt>
              <dd>{base}</dd>
            <% end %>
            <dt :if={turn.wall_seconds}>Time taken</dt>
            <dd :if={turn.wall_seconds}>
              {turn.wall_seconds} seconds of {Catalog.wall_cap(turn.test)}
            </dd>
            <dt :if={turn.model_spend_usd}>Model cost</dt>
            <dd :if={turn.model_spend_usd}>{Copy.dollars(turn.model_spend_usd)}</dd>
            <dt :if={turn.judgment}>Judged by</dt>
            <dd :if={turn.judgment}>{turn.judgment["model"]}</dd>
            <dt :if={turn.judge_cost_usd}>Judge cost</dt>
            <dd :if={turn.judge_cost_usd}>{Copy.dollars(turn.judge_cost_usd)}</dd>
          </dl>

          <details class="wallet-bench__files">
            <summary>The prompt sent</summary>
            <pre>{turn.prompt}</pre>
          </details>

          <div :if={turn.evidence} class="wallet-bench__files">
            <h3>Recorded files</h3>
            <p class="quiet">Secrets were blanked before anything was stored.</p>
            <ul>
              <li :for={{file, %{"bytes" => bytes}} <- Enum.sort(turn.evidence)}>
                <a href={
                  ~p"/wallet-bench/#{@attempt.id}/evidence/#{Catalog.turn_name(turn.test)}/#{file}"
                }>
                  {file}
                </a>
                <span class="quiet">{bytes} bytes</span>
              </li>
            </ul>
          </div>
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

  # The models that ruled on this attempt's turns, as each ruling recorded.
  defp judges(attempt) do
    attempt.turns |> Enum.filter(& &1.judgment) |> Enum.map(& &1.judgment["model"]) |> Enum.uniq()
  end

  defp version_note(%{"matches_survey" => true}), do: ", the same as the survey."

  defp version_note(%{"matches_survey" => false, "survey" => survey}),
    do: ", not the #{survey} the survey installed."

  defp version_note(%{"matches_survey" => nil}), do: "."
end
