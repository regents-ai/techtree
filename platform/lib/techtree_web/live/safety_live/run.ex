defmodule TechtreeWeb.SafetyLive.Run do
  @moduledoc """
  One comparison: the four numbers per monitor, the sentence that sets them
  against each other, and every case with the evidence behind each verdict.

  The page follows the run while it is going and keeps what it has when the
  run is cancelled or fails; the status line says which. A case opens in
  place, at an address that can be shared, and no case is hidden by default:
  the mistakes both monitors made together are the ones a reader most needs
  to see.
  """

  use TechtreeWeb, :live_view

  alias Techtree.Safety
  alias Techtree.Safety.Monitor
  alias Techtree.Safety.Scoring
  alias Techtree.Safety.TestPack

  @filters [all: "All", disagreements: "Disagreements", errors: "Errors"]

  @impl true
  def mount(%{"id" => id}, _session, socket) do
    case Safety.fetch_run(id) do
      {:ok, run} ->
        if connected?(socket), do: Phoenix.PubSub.subscribe(Techtree.PubSub, Safety.topic(run.id))
        {:ok, pack} = TestPack.fetch(run.test_slug)
        {:ok, a} = Monitor.fetch(run.monitor_a)
        {:ok, b} = Monitor.fetch(run.monitor_b)

        {:ok,
         assign(socket,
           page_title: "#{a.name} vs #{b.name} · Techtree Safety",
           run: run,
           pack: pack,
           a: a,
           b: b,
           filter: :all,
           expanded: nil
         )}

      :error ->
        raise TechtreeWeb.NotFoundError, "no comparison is recorded at that address"
    end
  end

  @impl true
  def handle_params(params, _uri, socket) do
    expanded =
      case Map.get(params, "case") do
        nil -> nil
        number -> Enum.find(socket.assigns.pack.cases, &(Integer.to_string(&1.number) == number))
      end

    {:noreply, assign(socket, expanded: expanded && expanded.id)}
  end

  @impl true
  def handle_event("filter", %{"filter" => filter}, socket) do
    chosen =
      if filter in ~w(all disagreements errors), do: String.to_existing_atom(filter), else: :all

    {:noreply, assign(socket, filter: chosen)}
  end

  def handle_event("cancel", _params, socket) do
    {:noreply, assign(socket, run: Safety.cancel(socket.assigns.run))}
  end

  # A run that has closed on this page stays closed. A verdict the runner
  # recorded just before the run was cancelled can arrive after the cancel
  # did, and it must not reopen the page: the page follows the run forward
  # only.
  @impl true
  def handle_info({:safety_run, run}, socket) do
    if socket.assigns.run.status == :running or run.status != :running,
      do: {:noreply, assign(socket, run: run)},
      else: {:noreply, socket}
  end

  @impl true
  def render(assigns) do
    score = Scoring.score(assigns.pack, assigns.run)

    assigns =
      assign(assigns,
        score: score,
        rows: Scoring.filter(score.rows, assigns.filter),
        tradeoff: Scoring.tradeoff(score, assigns.a, assigns.b),
        filters: filters(score)
      )

    ~H"""
    <Layouts.page>
      <article class="safety" aria-labelledby="run-title">
        <p class="back-link"><a href={~p"/safety/#{@pack.slug}"}>← {@pack.title}</a></p>
        <header class="page-heading">
          <p class="eyebrow">Techtree / Safety</p>
          <h1 id="run-title">{@a.name} vs {@b.name}</h1>
          <p id="run-status" class="lede">{status_words(@run, @score)}</p>
          <p :if={@run.failure} id="run-failure" class="quiet">{@run.failure}</p>
          <Regent.Primitives.button
            :if={@run.status == :running}
            id="cancel-run"
            type="button"
            variant="secondary"
            phx-click="cancel"
          >
            Cancel
          </Regent.Primitives.button>
        </header>

        <section class="section">
          <table id="comparison" class="comparison">
            <thead>
              <tr>
                <th scope="col"><span class="offscreen">Measure</span></th>
                <th scope="col">{@a.name}</th>
                <th scope="col">{@b.name}</th>
              </tr>
            </thead>
            <tbody>
              <tr id="missed-violations">
                <th scope="row">Missed violations</th>
                <td>{@score.a.missed} / {@score.violations}</td>
                <td>{@score.b.missed} / {@score.violations}</td>
              </tr>
              <tr id="false-alarms">
                <th scope="row">False alarms</th>
                <td>{@score.a.false_alarms} / {@score.compliant}</td>
                <td>{@score.b.false_alarms} / {@score.compliant}</td>
              </tr>
              <tr id="abstentions">
                <th scope="row">Abstentions</th>
                <td>{@score.a.abstentions} / {@score.total}</td>
                <td>{@score.b.abstentions} / {@score.total}</td>
              </tr>
              <tr id="errors">
                <th scope="row">Errors</th>
                <td>{@score.a.errors} / {@score.total}</td>
                <td>{@score.b.errors} / {@score.total}</td>
              </tr>
            </tbody>
          </table>
          <p id="tradeoff" class="safety__tradeoff">{@tradeoff}</p>
        </section>

        <section class="section">
          <p class="eyebrow">Cases</p>
          <div class="tasks__filters" aria-label="Filter cases">
            <Regent.Primitives.button
              :for={{filter, label, count} <- @filters}
              variant="secondary"
              id={"case-filter-#{filter}"}
              type="button"
              class="tasks__filter"
              aria-pressed={to_string(@filter == filter)}
              phx-click="filter"
              phx-value-filter={filter}
            >
              {label} {count}
            </Regent.Primitives.button>
          </div>
          <p class="case__row case__head" aria-hidden="true">
            <span>Case</span>
            <span>Actual outcome</span>
            <span>{@a.name}</span>
            <span>{@b.name}</span>
            <span></span>
          </p>
          <p :if={@rows == []} id="cases-empty" class="empty-state">{empty_words(@filter)}</p>
          <ol id="cases" class="cases">
            <li :for={row <- @rows} id={row.recorded.id} class="case">
              <.link
                patch={case_address(@run, row.recorded, @expanded)}
                class="case__row"
                aria-expanded={to_string(@expanded == row.recorded.id)}
                aria-controls={row.recorded.id <> "-detail"}
              >
                <span class="case__title">{row.recorded.title}</span>
                <span><span class="case__label">Actual outcome: </span>{outcome_words(
                  row.recorded.outcome
                )}</span>
                <span><span class="case__label">{@a.name}: </span>{verdict_words(row.a)}</span>
                <span><span class="case__label">{@b.name}: </span>{verdict_words(row.b)}</span>
                <span class="case__chevron" aria-hidden="true">{if @expanded == row.recorded.id,
                  do: "▴",
                  else: "▾"}</span>
              </.link>
              <div
                :if={@expanded == row.recorded.id}
                id={row.recorded.id <> "-detail"}
                class="case__detail"
              >
                <div>
                  <p class="eyebrow">Actual outcome</p>
                  <p><strong>{outcome_words(row.recorded.outcome)}.</strong> {row.recorded.record}</p>
                  <p class="quiet small">
                    Source: independent fixture record.
                    <a
                      :if={row.recorded.evidence_event}
                      href={event_anchor(row.recorded, row.recorded.evidence_event)}
                    >
                      Jump to event {row.recorded.evidence_event}
                    </a>
                  </p>
                </div>
                <div class="case__monitors">
                  <.finding preset={@a} verdict={row.a} recorded={row.recorded} />
                  <.finding preset={@b} verdict={row.b} recorded={row.recorded} />
                </div>
                <Regent.Primitives.disclosure
                  id={row.recorded.id <> "-transcript"}
                  summary="Full transcript"
                >
                  <p><strong>Task.</strong> {row.recorded.task}</p>
                  <ol class="transcript">
                    <li :for={event <- row.recorded.events} id={event_id(row.recorded, event.number)}>
                      <span class="transcript__kind">{event.kind}</span> {event.text}
                    </li>
                  </ol>
                </Regent.Primitives.disclosure>
              </div>
            </li>
          </ol>
        </section>

        <p class="safety__actions">
          <a id="compare-again" href={~p"/safety/#{@pack.slug}"}>Compare again</a>
          <a id="download-evidence" href={~p"/safety/runs/#{@run.id}/evidence"}>Download evidence</a>
        </p>
      </article>
    </Layouts.page>
    """
  end

  attr :preset, Monitor.Preset, required: true
  attr :verdict, :map, default: nil
  attr :recorded, TestPack.Case, required: true

  defp finding(assigns) do
    ~H"""
    <section class="finding">
      <p class="eyebrow">{@preset.name}</p>
      <p><strong>{verdict_words(@verdict)}</strong></p>
      <%= if @verdict do %>
        <p :if={@verdict["rationale"]} class="finding__rationale">“{@verdict["rationale"]}”</p>
        <p :if={@verdict["error"]} class="finding__rationale">{@verdict["error"]}</p>
        <p :if={@verdict["evidence_event"]} class="quiet small">
          Evidence: event {@verdict["evidence_event"]} ·
          <a href={event_anchor(@recorded, @verdict["evidence_event"])}>Jump to event</a>
        </p>
      <% end %>
    </section>
    """
  end

  defp filters(score) do
    Enum.map(@filters, fn {filter, label} ->
      {filter, label, length(Scoring.filter(score.rows, filter))}
    end)
  end

  defp case_address(run, recorded, expanded) do
    if expanded == recorded.id,
      do: ~p"/safety/runs/#{run.id}",
      else: ~p"/safety/runs/#{run.id}?case=#{recorded.number}"
  end

  defp event_id(recorded, number), do: "#{recorded.id}-event-#{number}"
  defp event_anchor(recorded, number), do: "#" <> event_id(recorded, number)

  defp status_words(run, score) do
    total = score.total

    case run.status do
      :running ->
        "Running · #{score.completed}/#{total} cases completed by both monitors"

      :complete ->
        "Complete · #{score.evaluated}/#{total} cases evaluated by both monitors · Test v#{run.test_version}"

      :cancelled ->
        "Cancelled · #{score.completed}/#{total} cases completed by both monitors before it stopped · Test v#{run.test_version}"

      :failed ->
        "Failed · #{score.completed}/#{total} cases completed by both monitors before it stopped · Test v#{run.test_version}"
    end
  end

  defp outcome_words(:violation), do: "Violation"
  defp outcome_words(:compliant), do: "Compliant"

  defp verdict_words(nil), do: "Pending"
  defp verdict_words(%{"verdict" => "flag"}), do: "Flag"
  defp verdict_words(%{"verdict" => "clear"}), do: "Clear"
  defp verdict_words(%{"verdict" => "abstain"}), do: "Abstained"
  defp verdict_words(%{"verdict" => "error"}), do: "Error"

  defp empty_words(:disagreements), do: "The monitors agreed on every case evaluated so far."
  defp empty_words(:errors), do: "No evaluation failed."
  defp empty_words(:all), do: "No cases."
end
