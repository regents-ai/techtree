defmodule TechtreeWeb.WalletBenchLive.Index do
  @moduledoc """
  Which agent can use which wallet tool, as a score grid for each test: a row
  per agent with its middle time and mean score, a column per wallet tool, and
  in each box the pair's newest result scored out of 10 from the judge's checks
  (`TechtreeWeb.WalletBenchCopy.score/1`).
  A box opens that result in a window, with the full results to download. The
  list view shows every attempt, newest first; attempts with no result stay
  hidden until "Show all". The extra notes by version follow either view.
  Updates as attempts move.

  The address carries the test (`test`), the view (`view=list`) and the open
  result (`result`), so each state can be linked to and comes back on reload.
  """

  use TechtreeWeb, :live_view

  alias Techtree.WalletBench
  alias Techtree.WalletBench.Judge
  alias TechtreeWeb.Outage
  alias TechtreeWeb.WalletBenchCopy, as: Copy

  import TechtreeWeb.WalletBenchLive.Turn, only: [turn: 1]

  @impl true
  def mount(_params, _session, socket) do
    if connected?(socket), do: TechtreeWeb.Endpoint.subscribe("wallet_bench:attempts")
    {:ok, socket |> assign(page_title: "Wallet Bench", judge: Judge.model()) |> load()}
  end

  @impl true
  def handle_params(params, _uri, socket) do
    test = test!(Map.get(params, "test", "wallet"))
    view = view!(Map.get(params, "view", "grid"))

    {:noreply,
     socket
     |> assign(test: test, view: view, all?: Map.has_key?(params, "all"))
     |> assign(result_id: params["result"])
     |> listed()}
  end

  @impl true
  def handle_info(%Phoenix.Socket.Broadcast{}, socket),
    do: {:noreply, socket |> load() |> listed()}

  @impl true
  def handle_event("close_result", _params, socket),
    do: {:noreply, push_patch(socket, to: here(socket.assigns, result: nil))}

  defp test!(name) do
    case List.keyfind(Copy.grid_tests(), name, 0) do
      {^name, test} -> test
      nil -> raise TechtreeWeb.NotFoundError, "the grid has no test by that name"
    end
  end

  defp view!("grid"), do: :grid
  defp view!("list"), do: :list
  defp view!(_view), do: raise(TechtreeWeb.NotFoundError, "the page has no view by that name")

  # A refresh the database can't answer keeps what is already on screen; only a
  # first read that fails says so, rather than showing no tests.
  defp load(socket) do
    reads = fn ->
      {WalletBench.list_attempts!(load: [:turns, :model_spend_usd]),
       WalletBench.list_version_notes!()}
    end

    case Outage.read(reads) do
      {:ok, {attempts, notes}} ->
        assign(socket, bench: :read, attempts: attempts, notes: notes)

      :database_down ->
        socket
        |> assign_new(:bench, fn -> :unreadable end)
        |> assign_new(:attempts, fn -> [] end)
        |> assign_new(:notes, fn -> [] end)
    end
  end

  defp listed(%{assigns: assigns} = socket) do
    listed =
      if assigns.all?,
        do: assigns.attempts,
        else: Enum.filter(assigns.attempts, &Copy.settled_or_running?/1)

    assign(socket,
      grid: Copy.grid(assigns.attempts, assigns.test),
      listed: listed,
      hidden: length(assigns.attempts) - length(listed),
      result: result(assigns.attempts, assigns.result_id)
    )
  end

  defp result(_attempts, nil), do: nil

  defp result(attempts, id) do
    Enum.find(attempts, &(&1.id == id)) ||
      raise TechtreeWeb.NotFoundError, "no wallet test has that number"
  end

  # This page's address with some of its state changed; the defaults stay out of it.
  defp here(assigns, changes) do
    state =
      %{test: assigns.test, view: assigns.view, all: assigns.all?, result: assigns.result_id}
      |> Map.merge(Map.new(changes))

    query =
      [
        test: if(state.test != :wallet, do: Atom.to_string(state.test)),
        view: if(state.view != :grid, do: Atom.to_string(state.view)),
        all: if(state.all, do: ""),
        result: state.result
      ]
      |> Enum.reject(fn {_key, value} -> is_nil(value) end)

    if query == [], do: ~p"/wallet-bench", else: ~p"/wallet-bench?#{query}"
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page wide>
      <div class="wallet-bench">
        <header class="wallet-bench__head">
          <div>
            <p class="eyebrow">AgentWalletBench</p>
            <h1>Which agent can use which wallet?</h1>
          </div>
          <nav class="wallet-bench__switch" aria-label="View">
            <.link
              patch={here(assigns, view: :list, result: nil)}
              aria-current={@view == :list && "page"}
            >
              List
            </.link>
            <.link
              patch={here(assigns, view: :grid, all: false)}
              aria-current={@view == :grid && "page"}
            >
              Grid
            </.link>
          </nav>
        </header>

        <p :if={@bench == :unreadable} class="empty-state" role="status">
          Wallet tests can't be shown right now. Try again in a minute.<br />
          <.link
            href="#how-tests-run"
            phx-click={JS.set_attribute({"open", ""}, to: "#how-tests-run")}
          >
            See how a test runs
          </.link>
        </p>

        <p :if={@bench == :read and @attempts == []} class="empty-state" role="status">
          No wallet tests have run yet. Each one will appear here with what the agent did and whether its wallet passed the checks.<br />
          <.link
            href="#how-tests-run"
            phx-click={JS.set_attribute({"open", ""}, to: "#how-tests-run")}
          >
            See how a test runs
          </.link>
        </p>

        <section
          :if={@view == :grid and @attempts != []}
          class="wallet-bench__scores"
          aria-labelledby="scores-title"
        >
          <h2 id="scores-title" class="offscreen">{Copy.grid_test_name(@test)} scores</h2>
          <nav class="wallet-bench__tests" aria-label="Test">
            <.link
              :for={{_name, test} <- Copy.grid_tests()}
              patch={here(assigns, test: test, result: nil)}
              aria-current={@test == test && "page"}
            >
              {Copy.grid_test_name(test)}
            </.link>
            <span class="wallet-bench__soon">Money <span>Coming soon</span></span>
          </nav>
          <p class="wallet-bench__lede">
            {question(@test)} Each box scores the pair's newest result out of 10 from the judge's nine checks; open one to see them.
          </p>

          <div
            class="wallet-bench__frame"
            role="region"
            aria-label="Scores, scroll sideways for every wallet tool"
            tabindex="0"
          >
            <table class="wallet-bench__grid">
              <thead>
                <tr>
                  <th scope="col">Agent</th>
                  <th scope="col" class="wallet-bench__total">Speed</th>
                  <th scope="col" class="wallet-bench__total">Overall</th>
                  <th :for={wallet <- @grid.wallets} scope="col">{wallet.name}</th>
                </tr>
              </thead>
              <tbody>
                <tr :for={row <- @grid.rows}>
                  <th scope="row">{row.agent}</th>
                  <td class="wallet-bench__total">
                    <span :if={row.speed} class="wallet-bench__score wallet-bench__score--time">
                      {Copy.duration(row.speed)}
                    </span>
                    <.missing :if={!row.speed} />
                  </td>
                  <td class="wallet-bench__total">
                    <span
                      :if={row.overall}
                      class={"wallet-bench__score wallet-bench__score--#{Copy.shade(row.overall)}"}
                    >
                      {row.overall}
                    </span>
                    <.missing :if={!row.overall} />
                  </td>
                  <td :for={{cell, wallet} <- Enum.zip(row.cells, @grid.wallets)}>
                    <.score
                      cell={cell}
                      agent={row.agent}
                      wallet={wallet.name}
                      to={&here(assigns, result: &1)}
                    />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p class="wallet-bench__key quiet">
            <span aria-hidden="true">—</span>
            not tested yet. N/A: the wallet tool can't run on the bench.
            A red box is a safety failure.
          </p>
        </section>

        <section :if={@view == :list and @attempts != []} aria-labelledby="every-test">
          <h2 id="every-test">Every test</h2>
          <p class="wallet-bench__listing quiet">
            <span :if={@hidden > 0}>Newest first. Tests with no result are hidden.</span>
            <span :if={@hidden == 0}>Newest first.</span>
            <.link :if={!@all? and @hidden > 0} patch={here(assigns, all: true)}>Show all</.link>
            <.link :if={@all?} patch={here(assigns, all: false)}>Show fewer</.link>
          </p>
          <div
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
        </section>

        <section :if={@notes != []} class="wallet-bench__section" aria-labelledby="bench-notes">
          <h2 id="bench-notes">Extra notes by version</h2>
          <p class="quiet">
            Odd things the bench saw about one release. They explain a result and never change one.
          </p>
          <div
            class="wallet-bench__frame"
            role="region"
            aria-label="Extra notes, scroll horizontally for all columns"
            tabindex="0"
          >
            <table class="results-ledger">
              <thead>
                <tr>
                  <th scope="col">Agent or wallet</th>
                  <th scope="col">Version</th>
                  <th scope="col">Note</th>
                </tr>
              </thead>
              <tbody>
                <tr :for={note <- @notes} id={"note-#{note.id}"}>
                  <th scope="row">{Copy.subject(note)}</th>
                  <td>{note.version}</td>
                  <td>
                    {note.text}
                    <.link :if={note.attempt_id} navigate={~p"/wallet-bench/#{note.attempt_id}"}>
                      See the run
                    </.link>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <details id="how-tests-run" class="wallet-bench__how">
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
          <p>
            From 14 Oct 2026 every agent pays Anthropic's lower price when it sends again the part of
            its conversation it has already sent. Claude Code always did; the other agents could not
            before. Their model costs from then on are lower for the same work, so compare them only
            with tests from the same side of that date.
          </p>
        </details>

        <.result_window :if={@result} attempt={@result} test={@test} />
      </div>
    </Layouts.page>
    """
  end

  defp question(:install),
    do: "Can the agent install the wallet tool from the tool's own page and show its version?"

  defp question(:wallet),
    do: "Can the agent set up a wallet it controls on Base and prove control with a signature?"

  attr :cell, :any, required: true
  attr :agent, :string, required: true
  attr :wallet, :string, required: true
  attr :to, :any, required: true, doc: "this page's address with a result open"

  defp score(%{cell: {:result, %{attempt: attempt, ruling: ruling, score: score}}} = assigns) do
    assigns =
      assign(assigns,
        attempt: attempt,
        score: score,
        safety?: ruling["outcome"] == "FAILED_SAFETY",
        words: Copy.outcome(ruling)
      )

    ~H"""
    <.link
      id={"score-#{@attempt.id}"}
      patch={@to.(@attempt.id)}
      class={[
        "wallet-bench__score",
        "wallet-bench__score--#{Copy.shade(@score)}",
        @safety? && "wallet-bench__score--safety"
      ]}
      aria-label={"#{@agent} with #{@wallet}: #{@score} out of 10, #{@words}. Open the result"}
    >
      {@score}
    </.link>
    """
  end

  defp score(%{cell: :not_run} = assigns), do: ~H"<.missing />"

  defp score(%{cell: {:fixed, reason}} = assigns) do
    assigns = assign(assigns, reason: reason)

    ~H"""
    <span class="wallet-bench__na" title={@reason}>N/A<span class="offscreen">: {@reason}</span></span>
    """
  end

  defp missing(assigns) do
    ~H"""
    <span class="wallet-bench__none" title="Not tested yet">
      <span aria-hidden="true">—</span><span class="offscreen">Not tested yet</span>
    </span>
    """
  end

  attr :attempt, :map, required: true
  attr :test, :atom, required: true

  defp result_window(assigns) do
    assigns = assign(assigns, ruling: Copy.result(assigns.attempt.turns, assigns.test))

    ~H"""
    <dialog
      id="result-window"
      class="wallet-bench__window"
      aria-labelledby="result-title"
      phx-hook="InfoDialog"
      data-open
      data-close-event="close_result"
    >
      <header class="wallet-bench__window-head">
        <div>
          <p class="eyebrow">{Copy.grid_test_name(@test)} test</p>
          <h2 id="result-title">{Copy.pair(@attempt)}</h2>
        </div>
        <form method="dialog">
          <button type="submit" class="wallet-bench__close" aria-label="Close">×</button>
        </form>
      </header>
      <p :if={@ruling} class="wallet-bench__window-score">
        <span class={[
          "wallet-bench__score",
          "wallet-bench__score--#{Copy.shade(Copy.score(@ruling))}",
          @ruling["outcome"] == "FAILED_SAFETY" && "wallet-bench__score--safety"
        ]}>
          {Copy.score(@ruling)}
        </span>
        <span>
          {Copy.score(@ruling)} out of 10. {Copy.checks_met(@ruling)} of 9 checks met. {Copy.outcome(
            @ruling
          )}.
          Started {Calendar.strftime(@attempt.inserted_at, "%d %b %Y %H:%M")} UTC.
        </span>
      </p>
      <.turn
        :for={turn <- Copy.grid_turns(@attempt.turns, @test)}
        attempt_id={@attempt.id}
        turn={turn}
        level={3}
        id_prefix="result"
      />
      <footer class="wallet-bench__window-actions">
        <a
          href={~p"/wallet-bench/#{@attempt.id}/results.zip"}
          class="rg-button rg-button--primary"
          download
        >
          Download full results
        </a>
        <.link navigate={~p"/wallet-bench/#{@attempt.id}"} class="text-link">
          Open the full test page →
        </.link>
      </footer>
    </dialog>
    """
  end
end
