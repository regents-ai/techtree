defmodule TechtreeWeb.RunsLive.Index do
  @moduledoc """
  Every run somebody has published, newest arrival first.

  This page is a log and not a table of standings, and the difference is the
  whole design of it. Entries are ordered by when they landed, newest first,
  and by nothing else. There is no position number, no "best", no control that
  would reorder them, and no way for a reader to ask for one — because an
  ordering is a ranking whatever it is called, and the Climb these runs belong
  to says in its own manifest that it has no leaderboard.

  Everything on a row was recomputed from bytes that verify, with one named
  exception. The publisher is the fingerprint of the key that signed the
  bundle; the agent and the model are what the campaign pinned; the scores come
  from a signed report whose own digest was checked. The exception is the
  Skill's name and GitHub link, which the publisher may send beside the signed
  bundle rather than inside it. Nothing checks them, so a row that shows either
  says, in its own words, that the publisher gave it and that it was not
  checked. Both are short labels of a fixed shape, never a sentence, which is
  why there is nothing on this page to moderate.

  Scores are rounded to three decimal places and otherwise shown as recorded.
  A Campaign names its score and the rule that decides between the two runs,
  and states no unit or range, so no mean is turned into a percentage and no
  bar pretends to know where the scale ends.

  The page repeats nothing typed into its address. An address it cannot read
  says so; one naming a selection with no Results names only the parts this
  site recognises.

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

  The page reads one keyset page at a time, twenty-five at a time, newest
  first, and the next page holds the entries that arrived before it — the same
  rule the read endpoint follows, so the two cannot disagree about what "the
  next page" means.

  The page says what the checking was and what it was not. This site checked
  that a receipt is internally consistent and signed by the key it names. It
  did not watch the run and did not repeat it. Both halves are on the page,
  because only one of them is a page about evidence.
  """

  use TechtreeWeb, :live_view

  alias Techtree.Catalog.Query, as: Catalog
  alias Techtree.Network.AgentVersions
  alias Techtree.Network.Query
  alias Techtree.Network.ResultFilters
  alias TechtreeWeb.ClimbCopy
  alias TechtreeWeb.ResultAssessment

  @impl true
  def mount(_params, _session, socket) do
    {:ok, assign(socket, page_title: "Published Results")}
  end

  @impl true
  def handle_params(params, _uri, socket) do
    families = Query.agent_families()

    socket =
      case Query.read_page_options(params) do
        {:ok, options} -> show_selection(socket, families, params, options)
        {:error, _reason} -> show_empty(socket, families, :unreadable, [])
      end

    {:noreply, socket}
  end

  defp show_selection(socket, families, params, options) do
    with {:ok, selection} <- AgentVersions.select(families, params),
         {:ok, filters} <- ResultFilters.select(selection, params) do
      page = Query.page(page_options(options, selection, filters))

      socket
      |> assign(
        families: families,
        selection: selection,
        filters: filters,
        page_limit: Map.get(params, "limit"),
        entries: page.entries,
        next_before_sequence: page.next_before_sequence,
        score_name: score_name(filters.challenge),
        empty: empty(page.entries, families, Map.has_key?(params, "before_sequence")),
        asked_for: []
      )
      |> pin_selection(selection, filters, params)
    else
      :error -> show_empty(socket, families, :no_match, asked_for(families, params))
    end
  end

  defp show_empty(socket, families, empty, asked_for) do
    assign(socket,
      families: families,
      selection: nil,
      filters: ResultFilters.empty(),
      page_limit: nil,
      entries: [],
      next_before_sequence: nil,
      score_name: nil,
      empty: empty,
      asked_for: asked_for
    )
  end

  defp page_options(options, nil, _filters), do: options

  defp page_options(options, selection, filters) do
    Keyword.merge(options,
      agent: selection.family.id,
      agent_version: selection.version,
      model: filters.model,
      challenge: filters.challenge
    )
  end

  # Resolve "latest" once, then retain that exact version through reloads
  # and reconnects even when a newer runtime is subsequently submitted.
  defp pin_selection(socket, nil, _filters, _params), do: socket

  defp pin_selection(socket, selection, filters, params) do
    if connected?(socket) &&
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
            <p id="results-scope" class="small quiet">
              Only Climb runs can be published today. A test of your own Skill stays on your
              computer; <.link navigate={~p"/examples/tdd"}>the tdd example</.link>
              shows what one looks like.
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

        <p :if={@empty == :log} class="runs-index__empty empty-state">
          Nobody has published a Result yet. Each Result comes from a Climb: the same agent on the same tasks, once without a Skill and once with it.
          <.link navigate={~p"/start"}>Start your first Climb</.link>
          to make one on your computer.
        </p>

        <p :if={@empty == :no_match} id="results-no-match" class="runs-index__empty empty-state">
          {no_match_words(@asked_for)}<br />
          <.link patch={~p"/results"}>Show the newest Results</.link>
        </p>

        <p :if={@empty == :unreadable} id="results-unreadable" class="runs-index__empty empty-state">
          This address doesn't describe a list of Results.<br />
          <.link patch={~p"/results"}>Show the newest Results</.link>
        </p>

        <p :if={@empty == :no_earlier} id="results-no-earlier" class="runs-index__empty empty-state">
          There are no earlier Results for {selection_words(@selection, @filters)}.
          <.link patch={results_url(@selection, @filters, @page_limit)}>Back to the newest page</.link>
        </p>

        <p :if={@entries != []} id="results-score-scale" class="section-note small quiet">
          Scores are each run's mean <code>{@score_name}</code>
          over its tasks, rounded to three decimal places. This Climb does not say what unit or range the score uses.
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
              Published Results, newest first. Scores are rounded to three decimal places. Δ is
              candidate minus baseline, not a rank.
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
                      aria-label={"GitHub link the publisher gave for #{skill_name(entry)}, not checked"}
                    >· GitHub ↗</a>
                  </small>
                  <small :if={publisher_words(entry)} id={"run-publisher-#{entry.log_sequence}"}>
                    {publisher_words(entry)}
                  </small>
                </th>
                <td :for={branch <- [:baseline_mean, :candidate_mean]} class="results-ledger__numeric">
                  {ResultAssessment.reward(Map.fetch!(entry, branch))}
                </td>
                <td class="results-ledger__numeric results-ledger__delta">
                  <strong>{ResultAssessment.change(entry.absolute_delta)}</strong>
                </td>
                <td class="results-ledger__tasks">
                  <span aria-label={task_words(entry)} title={task_words(entry)}>
                    {entry.wins} / {entry.ties} / {entry.losses}
                  </span>
                </td>
                <td class="results-ledger__date">
                  <time datetime={DateTime.to_iso8601(entry.accepted_at)}>
                    {arrived(entry.accepted_at)}
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

  # The name and the link travel beside the signed bundle, not inside it, so
  # the row says whose word they are.
  defp publisher_words(entry) do
    case {present(Map.get(entry, :skill_name)), github_url(entry)} do
      {nil, nil} -> nil
      {_name, nil} -> "Name given by the publisher; not checked"
      {nil, _url} -> "Link given by the publisher; not checked"
      {_name, _url} -> "Name and link given by the publisher; not checked"
    end
  end

  # The score a Campaign decides on, by the name it gives it. Ingest only
  # publishes a Result whose Campaign this site publishes, and a Climb is
  # retired rather than removed, so a chosen challenge always has one.
  defp score_name(nil), do: nil

  defp score_name(challenge) do
    {:ok, climb} = Catalog.get_any_climb_by_campaign_digest(challenge)
    climb.projection["scoring"]["primary_reward"]
  end

  # Which empty page a readable selection is, if any: nothing published at
  # all, a page past the oldest entry of a selection that has entries, or a
  # selection with no entries. An address the page cannot read at all, or one
  # naming a selection that does not exist, never gets this far.
  defp empty([_entry | _entries], _families, _earlier?), do: nil
  defp empty([], [], _earlier?), do: :log
  defp empty([], _families, true), do: :no_earlier
  defp empty([], _families, false), do: :no_match

  # What the address asked for, naming only what this site recognises: a
  # harness it has Results for, a version of that harness, a model a Result
  # names, and a Campaign this site publishes. Anything else is "that harness",
  # "that model" or "that challenge", so no text from an address is repeated.
  defp asked_for(families, params) do
    [
      params["agent"] && harness_words(families, params["agent"], params["agent_version"]),
      params["model"] && model_words(params["model"]),
      params["challenge"] && challenge_words(params["challenge"])
    ]
    |> Enum.reject(&is_nil/1)
  end

  defp harness_words(families, agent, version) do
    case Enum.find(families, &(&1.id == agent)) do
      nil ->
        "that harness"

      family ->
        if version in family.versions,
          do: "#{family.label} #{version}",
          else: "that version of #{family.label}"
    end
  end

  defp model_words(model) do
    if model in Query.result_models(), do: model, else: "that model"
  end

  defp challenge_words(challenge) do
    case Catalog.get_any_climb_by_campaign_digest(challenge) do
      {:ok, _climb} -> "challenge " <> ResultAssessment.short_digest(challenge)
      {:error, _unknown} -> "that challenge"
    end
  end

  defp no_match_words([]), do: "No published Results match this address."

  defp no_match_words(asked_for),
    do: "No published Results match this selection: " <> Enum.join(asked_for, " · ")

  defp selection_words(selection, filters) do
    challenge =
      Enum.find(filters.challenges, &(&1.campaign_spec_digest == filters.challenge))

    "#{selection.family.label} #{selection.version} · #{filters.model} · #{campaign_name(challenge)}"
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

  defp task_words(entry) do
    "#{entry.wins} better, #{entry.ties} same, #{entry.losses} worse"
  end

  defp arrived(at) do
    at
    |> DateTime.truncate(:second)
    |> Calendar.strftime("%Y-%m-%d %H:%M UTC")
  end

  defp withdrawn_words(at) do
    "Withdrawn by the participant on " <> Calendar.strftime(at, "%-d %B %Y")
  end
end
