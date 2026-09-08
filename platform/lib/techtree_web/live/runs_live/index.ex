defmodule TechtreeWeb.RunsLive.Index do
  @moduledoc """
  Every run somebody has published, in the order they arrived.

  This page is a log and not a table of standings, and the difference is the
  whole design of it. Entries are ordered by when they landed and by nothing
  else. There is no position number, no "best", no control that would reorder
  them, and no way for a reader to ask for one — because an ordering is a
  ranking whatever it is called, and the Climb these runs belong to says in its
  own manifest that it has no leaderboard.

  Everything on a row was recomputed from bytes that verify. The publisher is
  the fingerprint of the key that signed the bundle; the agent and the model
  are what the campaign pinned; the scores come from a signed report whose own
  digest was checked. There is no field here a submitter could write a sentence
  into, which is why there is nothing on this page to moderate.

  A withdrawn run keeps its row and says so. Withdrawal is an event appended to
  the log rather than a hole punched in it, and a log that quietly dropped its
  withdrawn entries would be a log with gaps nothing explained.

  The log did not open empty: this project's own certification runs went on it
  first, through the same address as everybody else's. The page says so in one
  sentence of its own. It is not said on a row, and it deliberately cannot be:
  a row carries only what was signed, so a badge reading "ours" would be the
  one unverifiable claim on a page whose whole point is that it has none. A
  sentence the page makes about itself is a different kind of thing — a reader
  can weigh who is saying it, which is exactly what they cannot do with a
  label sitting on somebody's result.

  The page reads one keyset page at a time, twenty-five at a time, oldest link
  first — the same rule the read endpoint follows, so the two cannot disagree
  about what "the next page" means.

  The page says what the checking was and what it was not. This site checked
  that a receipt is internally consistent and signed by the key it names. It
  did not watch the run and did not repeat it. Both halves are on the page,
  because only one of them is a page about evidence.
  """

  use TechtreeWeb, :live_view

  alias Techtree.Network.Query
  alias TechtreeWeb.ClimbCopy
  alias Techtree.Network.AgentVersions
  alias Techtree.Network.ResultFilters

  @impl true
  def mount(_params, _session, socket) do
    {:ok, assign(socket, page_title: "Published Results")}
  end

  @impl true
  def handle_params(params, _uri, socket) do
    families = Query.agent_families()

    {selection, filters, page, error} =
      with {:ok, options} <- Query.read_page_options(params),
           {:ok, selection} <- AgentVersions.select(families, params),
           {:ok, filters} <- ResultFilters.select(selection, params) do
        options =
          if selection,
            do:
              Keyword.merge(options,
                agent: selection.family.id,
                agent_version: selection.version,
                model: filters.model,
                challenge: filters.challenge
              ),
            else: options

        {selection, filters, Query.page(options), nil}
      else
        {:error, message} ->
          {nil, ResultFilters.empty(), %{entries: [], next_before_sequence: nil}, message}
      end

    socket =
      assign(socket,
        families: families,
        selection: selection,
        filters: filters,
        page_limit: Map.get(params, "limit"),
        selection_error: error,
        entries: page.entries,
        next_before_sequence: page.next_before_sequence
      )

    # Resolve "latest" once, then retain that exact version through reloads
    # and reconnects even when a newer runtime is subsequently submitted.
    socket =
      if connected?(socket) && selection &&
           Enum.any?(~w(agent agent_version model challenge), &(!Map.has_key?(params, &1))) do
        push_patch(socket,
          to:
            AgentVersions.url(selection.family.id, selection.version,
              model: filters.model,
              challenge: filters.challenge,
              before_sequence: Map.get(params, "before_sequence"),
              limit: Map.get(params, "limit")
            ),
          replace: true
        )
      else
        socket
      end

    {:noreply, socket}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page wide flush>
      <div class="runs-index">
        <section class="runs-index__intro" aria-labelledby="runs-index-title">
          <header class="page-heading runs-index__heading">
            <p class="eyebrow">The public run log</p>
            <h1 id="runs-index-title">Published Results</h1>
            <p class="runs-index__lede">
              One harness. One model. One challenge. Inspect what changed when a Skill changed.
              Newest submissions first, not ranked by score.
            </p>
          </header>
        </section>

        <section class="results-filters" aria-label="Filter published Results">
          <div class="results-filter-row">
            <h2 class="results-filter-label"><span>01</span> Harness</h2>
            <div id="agent-version-browser" phx-hook="AgentVersions" aria-label="Agent versions">
              <p :if={@families == []} class="quiet small">No submitted harnesses yet</p>
              <nav class="agent-versions__families" aria-label="Agent families">
                <.link
                  :for={family <- @families}
                  patch={AgentVersions.url(family.id, hd(family.versions))}
                  aria-current={if @selection && @selection.family.id == family.id, do: "page"}
                >
                  {family.label}
                </.link>
              </nav>
              <div :if={@selection} class="agent-versions__carousel">
                <.link
                  :if={@selection.newer}
                  id="agent-version-newer"
                  patch={AgentVersions.url(@selection.family.id, @selection.newer)}
                  aria-label="Newer agent version"
                >← Newer</.link>
                <nav class="agent-versions__list" aria-label="Submitted versions">
                  <.link
                    :for={version <- @selection.family.versions}
                    patch={AgentVersions.url(@selection.family.id, version)}
                    aria-current={if version == @selection.version, do: "page"}
                  >
                    {version}<span :if={version == @selection.latest}> · Latest submitted</span>
                  </.link>
                </nav>
                <.link
                  :if={@selection.older}
                  id="agent-version-older"
                  patch={AgentVersions.url(@selection.family.id, @selection.older)}
                  aria-label="Older agent version"
                >Older →</.link>
              </div>
            </div>
          </div>
          <div class="results-filter-row">
            <h2 class="results-filter-label"><span>02</span> Model</h2>
            <nav class="results-filter-choices" aria-label="Submitted models">
              <.link
                :for={model <- @filters.models}
                class="result-choice"
                patch={AgentVersions.url(@selection.family.id, @selection.version, model: model)}
                aria-current={if model == @filters.model, do: "page"}
              >{model}</.link>
              <p :if={@filters.models == []} class="quiet small">Choose a submitted harness first</p>
            </nav>
          </div>
          <div class="results-filter-row">
            <h2 class="results-filter-label"><span>03</span> Challenge</h2>
            <nav class="results-filter-choices" aria-label="Submitted challenges">
              <.link
                :for={challenge <- @filters.challenges}
                class="result-choice"
                title={challenge.campaign_spec_digest}
                patch={
                  AgentVersions.url(@selection.family.id, @selection.version,
                    model: @filters.model,
                    challenge: challenge.campaign_spec_digest
                  )
                }
                aria-current={if challenge.campaign_spec_digest == @filters.challenge, do: "page"}
              >
                {campaign_name(challenge)}
                <span class="result-choice__digest">{String.slice(
                  challenge.campaign_spec_digest,
                  7,
                  8
                )}</span>
              </.link>
              <p :if={@filters.challenges == []} class="quiet small">
                Choose a submitted model first
              </p>
            </nav>
          </div>
        </section>

        <p :if={@selection} id="agent-version-summary" class="results-context" aria-live="polite">
          {@selection.family.label} {@selection.version} · {@filters.model}
          <span>Participant-attested · Not independently reproduced</span>
        </p>

        <p :if={@selection_error} id="agent-version-error" role="alert">{@selection_error}</p>
        <.link :if={@selection_error} patch={~p"/results"} class="text-link">Reset filters →</.link>

        <p
          :if={@entries == [] && !@selection_error && @families == []}
          class="runs-index__empty empty-state"
        >
          Nobody has published a Result yet.
          <.link navigate={~p"/start"}>Start your first Climb</.link>
          to create one locally.
        </p>

        <p :if={@entries == [] && @selection} class="empty-state">
          No earlier Results for this agent version.
          <.link patch={results_url(@selection, @filters, @page_limit)}>Newest Results</.link>
        </p>

        <div
          :if={@entries != []}
          class="runs-index__table-frame"
          role="region"
          aria-label="Published Results table, scroll horizontally for all columns"
          tabindex="0"
        >
          <table class="results-ledger">
            <caption>
              Published Results, newest first. Means within 0–1 are shown as percentages;
              other scores retain their raw scale. Δ is candidate minus baseline, not a rank.
            </caption>
            <thead>
              <tr>
                <th scope="col">Skill comparison</th>
                <th scope="col" class="results-ledger__numeric">Baseline</th>
                <th scope="col" class="results-ledger__numeric">Candidate</th>
                <th scope="col" class="results-ledger__numeric">Δ Score</th>
                <th scope="col">Tasks <span class="quiet">↑ / = / ↓</span></th>
                <th scope="col">Published</th>
                <th scope="col">Evidence</th>
              </tr>
            </thead>
            <tbody>
              <tr
                :for={entry <- @entries}
                id={"run-entry-#{entry.log_sequence}"}
                class={["results-ledger__row", entry.withdrawn_at && "is-withdrawn"]}
              >
                <th scope="row" class="results-ledger__skill">
                  <a href={entry_url(entry)}>{skill_name(entry)}</a>
                  <small>
                    vs baseline
                    <a
                      :if={github_url(entry)}
                      id={"run-github-#{entry.log_sequence}"}
                      href={github_url(entry)}
                      target="_blank"
                      rel="noopener noreferrer"
                      aria-label={"View #{skill_name(entry)} on GitHub"}
                    >· GitHub ↗</a>
                  </small>
                </th>
                <td :for={branch <- [:baseline_mean, :candidate_mean]} class="results-ledger__numeric">
                  <span>{score_label(entry, branch)}</span>
                  <svg
                    :if={normalized_pair?(entry)}
                    class={["score-strip", branch == :candidate_mean && "score-strip--candidate"]}
                    viewBox="0 0 100 4"
                    preserveAspectRatio="none"
                    aria-hidden="true"
                  >
                    <path d="M0 2H100" stroke="currentColor" stroke-opacity="0.18" stroke-width="4" />
                    <rect
                      x="0"
                      y="0"
                      width={Float.round(Map.fetch!(entry, branch) * 100, 1)}
                      height="4"
                      fill="currentColor"
                    />
                  </svg>
                </td>
                <td class="results-ledger__numeric results-ledger__delta">
                  <strong>{uplift_value(entry)}</strong>
                </td>
                <td class="results-ledger__tasks">
                  <span aria-label={task_words(entry)} title={task_words(entry)}>
                    {entry.wins} / {entry.ties} / {entry.losses}
                  </span>
                </td>
                <td class="results-ledger__date">
                  <time
                    datetime={DateTime.to_iso8601(entry.accepted_at)}
                    title={arrived(entry.accepted_at)}
                  >
                    {compact_arrived(entry.accepted_at)}
                  </time>
                </td>
                <td class="results-ledger__evidence">
                  <a href={entry_url(entry)} aria-label={"Inspect evidence for #{skill_name(entry)}"}>Inspect →</a>
                  <small :if={entry.withdrawn_at} title={withdrawn_words(entry.withdrawn_at)}>Withdrawn</small>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <p :if={@next_before_sequence} class="runs-index__pagination">
          <.link
            class="text-link"
            patch={results_url(@selection, @filters, @page_limit, @next_before_sequence)}
          >
            Earlier Results <span aria-hidden="true">→</span>
          </.link>
        </p>

        <p :if={@entries != []} class="runs-index__provenance small quiet">
          The first entries are Techtree’s own release-check Results. They use the same format,
          checks, and ordering as every other published Result.
        </p>

        <p class="runs-index__footer small quiet">
          <a href={~p"/verify"}>How verification works</a>
        </p>
      </div>
    </Layouts.page>
    """
  end

  # A digest carries a colon, which the route sigil would escape into an
  # address a reader could not compare against the one they hold.
  defp entry_url(entry), do: "/results/" <> entry.bundle_digest

  defp campaign_name(entry) do
    copy = legacy_copy(entry)

    present(Map.get(entry, :campaign_name)) || Map.get(copy, :campaign_title) ||
      entry.climb_reference
  end

  defp skill_name(entry) do
    copy = legacy_copy(entry)

    present(Map.get(entry, :skill_name)) || Map.get(copy, :candidate_skill_label) ||
      "the candidate Skill"
  end

  defp github_url(entry) do
    case Map.get(entry, :skill_github_url) do
      "https://github.com/" <> _ = url -> url
      _other -> nil
    end
  end

  defp legacy_copy(entry), do: ClimbCopy.for_reference(entry.climb_reference) || %{}

  defp present(value) when is_binary(value) do
    if String.trim(value) == "", do: nil, else: value
  end

  defp present(_value), do: nil

  defp results_url(selection, filters, limit, sequence \\ nil),
    do:
      AgentVersions.url(selection.family.id, selection.version,
        model: filters.model,
        challenge: filters.challenge,
        limit: limit,
        before_sequence: sequence
      )

  defp normalized_pair?(entry),
    do: normalized_score?(entry.baseline_mean) and normalized_score?(entry.candidate_mean)

  defp score_label(entry, branch) do
    value = Map.fetch!(entry, branch)

    if normalized_pair?(entry),
      do: "#{Float.round(value * 100, 1)}%",
      else: "#{Float.round(value, 3)}"
  end

  defp uplift_value(entry) do
    if normalized_score?(entry.baseline_mean) and normalized_score?(entry.candidate_mean) do
      score_points(entry.absolute_delta)
    else
      signed_delta(entry.absolute_delta)
    end
  end

  defp score_points(delta) do
    percent = Float.round(delta * 100, 1)

    if percent > 0, do: "+#{percent} pts", else: "#{percent} pts"
  end

  defp signed_delta(delta) do
    rounded = Float.round(delta, 3)

    if rounded > 0, do: "+#{rounded}", else: to_string(rounded)
  end

  defp normalized_score?(score), do: score >= 0 and score <= 1

  defp task_words(entry) do
    "#{entry.wins} better, #{entry.ties} same, #{entry.losses} worse"
  end

  defp arrived(at) do
    at
    |> DateTime.truncate(:second)
    |> Calendar.strftime("%Y-%m-%d %H:%M UTC")
  end

  defp compact_arrived(at), do: Calendar.strftime(at, "%d %b · %H:%M")

  defp withdrawn_words(at) do
    "Withdrawn by the participant on " <> Calendar.strftime(at, "%-d %B %Y")
  end
end
