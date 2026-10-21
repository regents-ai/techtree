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
  Each Climb's page says how its tasks are scored, so no mean is turned into a
  percentage here and no bar pretends to know where the scale ends.

  Filters narrow the log and never hide any of it by default. Each one offers
  every value the filters before it leave, plus "All", and an address that
  chooses nothing shows every Result. The page says how many Results match out
  of how many there are.

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
  alias Techtree.Catalog.Route
  alias Techtree.Network.AgentVersions
  alias Techtree.Network.Query
  alias Techtree.Network.ResultFilters
  alias Techtree.Network.Verdict
  alias TechtreeWeb.ModelAccess
  alias TechtreeWeb.Outage
  alias TechtreeWeb.ResultAssessment
  alias TechtreeWeb.ResultNames

  @impl true
  def mount(_params, _session, socket) do
    {:ok, assign(socket, page_title: "Published Results")}
  end

  @impl true
  def handle_params(params, _uri, socket) do
    case Outage.read(fn -> show(socket, params) end) do
      {:ok, socket} -> {:noreply, socket}
      :database_down -> {:noreply, show_empty(socket, [], :database_down, [])}
    end
  end

  defp show(socket, params) do
    families = Query.agent_families()

    case Query.read_page_options(params) do
      {:ok, options} -> show_selection(socket, families, params, options)
      {:error, _reason} -> show_empty(socket, families, :unreadable, [])
    end
  end

  defp show_selection(socket, families, params, options) do
    with {:ok, selection} <- AgentVersions.select(families, params),
         {:ok, filters} <- ResultFilters.select(selection, params) do
      chosen = chosen(selection, filters)
      page = Query.page(Keyword.merge(options, query_options(chosen)))
      climb = chosen_climb(filters.challenge)

      assign(socket,
        families: families,
        selection: selection,
        filters: filters,
        chosen: chosen,
        page_limit: Map.get(params, "limit"),
        entries: page.entries,
        runs: page.runs,
        next_before_sequence: page.next_before_sequence,
        matching: Query.count(query_options(chosen)),
        total: Query.count(),
        climb_slug: climb && climb.projection["slug"],
        empty: empty(page.entries, families, Map.has_key?(params, "before_sequence")),
        asked_for: []
      )
    else
      :error -> show_empty(socket, families, :no_match, asked_for(families, params))
    end
  end

  defp show_empty(socket, families, empty, asked_for) do
    assign(socket,
      families: families,
      selection: nil,
      filters: ResultFilters.empty(),
      chosen: [],
      page_limit: nil,
      entries: [],
      runs: %{},
      next_before_sequence: nil,
      matching: 0,
      total: if(empty == :database_down, do: 0, else: Query.count()),
      climb_slug: nil,
      empty: empty,
      asked_for: asked_for
    )
  end

  # The coordinates the address chose, in the order each one narrows the next.
  defp chosen(selection, filters) do
    [
      agent: selection && selection.family.id,
      agent_version: selection && selection.version,
      model: filters.model,
      challenge: filters.challenge,
      route: filters.route
    ]
  end

  defp query_options(chosen) do
    chosen
    |> Keyword.take([:agent, :agent_version, :model, :challenge])
    |> Keyword.put(:provider, chosen[:route] && Route.provider!(chosen[:route]))
  end

  # Choosing one coordinate keeps those before it and clears those after it,
  # which the new choice may no longer leave.
  @order [:agent, :agent_version, :model, :challenge, :route]

  defp choose(chosen, key, value) do
    chosen
    |> Keyword.take(Enum.take_while(@order, &(&1 != key)))
    |> Keyword.put(key, value)
    |> AgentVersions.url()
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

        <section
          :if={@total > 0}
          class="results-filters"
          aria-label="Filter published Results"
        >
          <div class="results-filter-row">
            <h2 class="results-filter-label"><span>01</span> Harness</h2>
            <div id="agent-version-browser" phx-hook="AgentVersions" aria-label="Agent versions">
              <nav class="agent-versions__families" aria-label="Agent families">
                <.link
                  patch={choose(@chosen, :agent, nil)}
                  aria-current={if is_nil(@selection), do: "page"}
                >
                  All harnesses
                </.link>
                <.link
                  :for={family <- @families}
                  patch={choose(@chosen, :agent, family.id)}
                  aria-current={if @selection && @selection.family.id == family.id, do: "page"}
                >
                  {family.label}
                </.link>
              </nav>
              <div :if={@selection} class="agent-versions__carousel">
                <.link
                  :if={@selection.newer}
                  id="agent-version-newer"
                  patch={choose(@chosen, :agent_version, @selection.newer)}
                  aria-label="Newer agent version"
                >← Newer</.link>
                <nav class="agent-versions__list" aria-label="Submitted versions">
                  <.link
                    patch={choose(@chosen, :agent_version, nil)}
                    aria-current={if is_nil(@selection.version), do: "page"}
                  >
                    All versions
                  </.link>
                  <.link
                    :for={version <- @selection.family.versions}
                    patch={choose(@chosen, :agent_version, version)}
                    aria-current={if version == @selection.version, do: "page"}
                  >
                    {version}<span :if={version == @selection.latest}> · Latest submitted</span>
                  </.link>
                </nav>
                <.link
                  :if={@selection.older}
                  id="agent-version-older"
                  patch={choose(@chosen, :agent_version, @selection.older)}
                  aria-label="Older agent version"
                >Older →</.link>
              </div>
            </div>
            <a
              :if={@selection && harness_page(@selection.family.id)}
              class="text-link results-filter-about"
              href={harness_page(@selection.family.id)}
              target="_blank"
              rel="noopener noreferrer"
            >
              About {@selection.family.label} ↗
            </a>
          </div>
          <div class="results-filter-row">
            <h2 class="results-filter-label"><span>02</span> Model</h2>
            <nav class="results-filter-choices" aria-label="Submitted models">
              <.link
                :if={@filters.models != []}
                class="result-choice"
                patch={choose(@chosen, :model, nil)}
                aria-current={if is_nil(@filters.model), do: "page"}
              >All models</.link>
              <.link
                :for={model <- @filters.models}
                class="result-choice"
                patch={choose(@chosen, :model, model)}
                aria-current={if model == @filters.model, do: "page"}
              >{model}</.link>
            </nav>
          </div>
          <div class="results-filter-row">
            <h2 class="results-filter-label"><span>03</span> Challenge</h2>
            <nav class="results-filter-choices" aria-label="Submitted challenges">
              <.link
                :if={@filters.challenges != []}
                class="result-choice"
                patch={choose(@chosen, :challenge, nil)}
                aria-current={if is_nil(@filters.challenge), do: "page"}
              >All challenges</.link>
              <.link
                :for={challenge <- @filters.challenges}
                class="result-choice"
                title={challenge.campaign_spec_digest}
                patch={choose(@chosen, :challenge, challenge.campaign_spec_digest)}
                aria-current={if challenge.campaign_spec_digest == @filters.challenge, do: "page"}
              >
                {ResultNames.campaign(challenge)}
                <span class="result-choice__digest">{String.slice(
                  challenge.campaign_spec_digest,
                  7,
                  8
                )}</span>
              </.link>
            </nav>
            <a
              :if={@climb_slug}
              class="text-link results-filter-about"
              href={~p"/climbs/#{@climb_slug}"}
              target="_blank"
              rel="noopener noreferrer"
            >
              About this Climb ↗
            </a>
          </div>
          <div class="results-filter-row">
            <h2 class="results-filter-label"><span>04</span> Ran on</h2>
            <nav class="results-filter-choices" aria-label="Routes the Results ran on">
              <.link
                :if={@filters.routes != []}
                class="result-choice"
                patch={choose(@chosen, :route, nil)}
                aria-current={if is_nil(@filters.route), do: "page"}
              >All routes</.link>
              <.link
                :for={route <- @filters.routes}
                class="result-choice"
                patch={choose(@chosen, :route, route)}
                aria-current={if route == @filters.route, do: "page"}
              >{ModelAccess.label!(route)}</.link>
            </nav>
          </div>
        </section>

        <p :if={@entries != []} id="results-count" class="results-context" aria-live="polite">
          Showing {@matching} of {@total} {results_word(@total)}
          <span>Participant-attested · Integrity-checked · Not independently reproduced</span>
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

        <p
          :if={@empty == :database_down}
          class="runs-index__empty empty-state"
          role="status"
        >
          Results can't be shown right now. Try again in a minute.<br />
          <.link navigate={~p"/verify"}>See how to check a Result yourself</.link>
        </p>

        <p :if={@empty == :no_earlier} id="results-no-earlier" class="runs-index__empty empty-state">
          {no_earlier_words(@selection, @filters)}
          <.link patch={AgentVersions.url(@chosen ++ [limit: @page_limit])}>
            Back to the newest page
          </.link>
        </p>

        <p :if={@entries != []} id="results-score-scale" class="section-note small quiet">
          Scores are each run's mean task score over its tasks, rounded to three decimal places. Each Climb's page says how its tasks are scored.
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
                <th scope="col">Verdict</th>
                <th scope="col">Ran on</th>
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
                  <a href={entry_url(entry)}>{ResultNames.skill(entry)}</a>
                  <small>
                    vs baseline
                    <a
                      :if={github_url(entry)}
                      id={"run-github-#{entry.log_sequence}"}
                      href={github_url(entry)}
                      target="_blank"
                      rel="noopener noreferrer"
                      aria-label={"GitHub link the publisher gave for #{ResultNames.skill(entry)}, not checked"}
                    >· GitHub ↗</a>
                  </small>
                  <small :if={publisher_words(entry)} id={"run-publisher-#{entry.log_sequence}"}>
                    {publisher_words(entry)}
                  </small>
                  <small class="results-ledger__coordinates">{ResultNames.coordinates(entry)}</small>
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
                <td class="results-ledger__verdict">
                  <span class={["verdict", "verdict--#{verdict(entry)}"]}>
                    {ResultAssessment.label(verdict(entry))}
                  </span>
                  <small>{ResultAssessment.runs_words(Map.fetch!(@runs, entry.bundle_digest))}</small>
                </td>
                <td class="results-ledger__route">{ModelAccess.ran_on!(entry.subject_provider)}</td>
                <td class="results-ledger__date">
                  <time datetime={DateTime.to_iso8601(entry.accepted_at)}>
                    {arrived(entry.accepted_at)}
                  </time>
                </td>
                <td class="results-ledger__evidence">
                  <a
                    href={entry_url(entry)}
                    aria-label={"Inspect evidence for #{ResultNames.skill(entry)}"}
                  >Inspect →</a>
                  <small :if={entry.withdrawn_at} title={withdrawn_words(entry.withdrawn_at)}>Withdrawn</small>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <p :if={@next_before_sequence} class="runs-index__pagination">
          <.link
            class="text-link"
            patch={
              AgentVersions.url(
                @chosen ++ [limit: @page_limit, before_sequence: @next_before_sequence]
              )
            }
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

  defp github_url(entry) do
    case Map.get(entry, :skill_github_url) do
      "https://github.com/" <> _ = url -> url
      _other -> nil
    end
  end

  # The name and the link travel beside the signed bundle, not inside it, so
  # the row says whose word they are.
  defp publisher_words(entry) do
    case {Map.get(entry, :skill_name), github_url(entry)} do
      {nil, nil} -> nil
      {_name, nil} -> "Name given by the publisher; not checked"
      {nil, _url} -> "Link given by the publisher; not checked"
      {_name, _url} -> "Name and link given by the publisher; not checked"
    end
  end

  # The score a Campaign decides on, by the name it gives it. Ingest only
  # publishes a Result whose Campaign this site publishes, and a Climb is
  # retired rather than removed, so a chosen challenge always has one.
  defp chosen_climb(nil), do: nil

  defp chosen_climb(challenge) do
    {:ok, climb} = Catalog.get_any_climb_by_campaign_digest(challenge)
    climb
  end

  defp harness_page("hermes-agent"), do: "https://github.com/NousResearch/hermes-agent"
  defp harness_page("codex"), do: "https://github.com/openai/codex"
  defp harness_page(_id), do: nil

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
      params["challenge"] && challenge_words(params["challenge"]),
      params["route"] && route_words(params["route"])
    ]
    |> Enum.reject(&is_nil/1)
  end

  defp harness_words(families, agent, version) do
    case Enum.find(families, &(&1.id == agent)) do
      nil ->
        "that harness"

      family when is_nil(version) ->
        family.label

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

  defp route_words(route) do
    if route in Route.all(), do: "on your " <> ModelAccess.name!(route), else: "that route"
  end

  defp no_match_words([]), do: "No published Results match this address."

  defp no_match_words(asked_for),
    do: "No published Results match this selection: " <> Enum.join(asked_for, " · ")

  defp no_earlier_words(selection, filters) do
    case chosen_words(selection, filters) do
      [] -> "There are no earlier Results."
      words -> "There are no earlier Results for " <> Enum.join(words, " · ") <> "."
    end
  end

  defp chosen_words(selection, filters) do
    [
      harness_choice(selection),
      filters.model,
      challenge_choice(filters),
      filters.route && "on your " <> ModelAccess.name!(filters.route)
    ]
    |> Enum.reject(&is_nil/1)
  end

  defp harness_choice(nil), do: nil
  defp harness_choice(%{family: family, version: nil}), do: family.label
  defp harness_choice(%{family: family, version: version}), do: "#{family.label} #{version}"

  defp challenge_choice(%{challenge: nil}), do: nil

  defp challenge_choice(filters) do
    filters.challenges
    |> Enum.find(&(&1.campaign_spec_digest == filters.challenge))
    |> ResultNames.campaign()
  end

  defp verdict(entry), do: Verdict.of(entry.assessment)

  defp results_word(1), do: "Result"
  defp results_word(_count), do: "Results"

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
