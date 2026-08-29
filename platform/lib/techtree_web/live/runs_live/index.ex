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

  @impl true
  def mount(_params, _session, socket) do
    {:ok, assign(socket, page_title: "Published proofs")}
  end

  @impl true
  def handle_params(params, _uri, socket) do
    options =
      case Query.read_page_options(params) do
        {:ok, options} -> options
        {:error, _message} -> []
      end

    page = Query.page(options)

    {:noreply,
     assign(socket, entries: page.entries, next_before_sequence: page.next_before_sequence)}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page wide flush>
      <div class="runs-index">
        <section class="runs-index__intro" aria-labelledby="runs-index-title">
          <header class="page-heading runs-index__heading">
            <p class="eyebrow">Participant-attested</p>
            <h1 id="runs-index-title">Published proofs</h1>
            <p class="runs-index__lede">
              Proofs of controlled agent improvement. Each proof binds a published Climb, a paired task result, and the
              participant-controlled key that signed it. Techtree checks the bundle’s integrity
              and internal consistency. It does not claim to have witnessed or independently
              reproduced the run. This is a record, not a leaderboard.
            </p>
          </header>
        </section>

        <p :if={@entries == []} class="runs-index__empty empty-state">
          Nobody has published a proof yet. This is where the first one will appear.
        </p>

        <div :if={@entries != []} class="runs-index__table-frame">
          <div class="runs-table__header" aria-hidden="true">
            <span>Skill comparison</span>
            <span title="Change in score, shown on a 0–100 scale">Uplift</span>
            <span>Climb</span>
            <span>Run setup</span>
            <span>Tasks</span>
            <span>Attestation</span>
            <span>Published</span>
          </div>
          <ol class="runs-table" aria-label="Published proofs, newest first">
            <li
              :for={entry <- @entries}
              id={"run-entry-#{entry.log_sequence}"}
              class={["runs-table__row", entry.withdrawn_at && "runs-table__row--withdrawn"]}
            >
              <div class="runs-table__cell runs-table__comparison">
                <a class="runs-table__primary-link" href={entry_url(entry)}>
                  <strong>{skill_name(entry)}</strong>
                  <span>vs No Skill</span>
                </a>
                <a
                  :if={github_url(entry)}
                  class="github-link github-link--small"
                  id={"run-github-#{entry.log_sequence}"}
                  href={github_url(entry)}
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label={"View #{skill_name(entry)} on GitHub"}
                >
                  <svg viewBox="0 0 16 16" aria-hidden="true">
                    <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82A7.65 7.65 0 0 1 8 4.36c.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z" />
                  </svg>
                </a>
                <span :if={entry.withdrawn_at} class="runs-table__withdrawn">
                  {withdrawn_words(entry.withdrawn_at)}
                </span>
              </div>
              <div class="runs-table__cell runs-table__uplift">
                <strong aria-label={uplift_words(entry)}>
                  {uplift_value(entry)}
                </strong>
              </div>
              <div class="runs-table__cell runs-table__campaign" title={campaign_name(entry)}>
                {campaign_name(entry)}
              </div>
              <div class="runs-table__cell runs-table__runtime">
                <span title={entry.subject_model}>{entry.subject_model}</span>
                <small>{entry.subject_harness} {entry.subject_harness_version}</small>
              </div>
              <div class="runs-table__cell runs-table__tasks">
                <span title={task_words(entry)}>
                  {entry.wins} / {entry.ties} / {entry.losses}
                </span>
              </div>
              <div class="runs-table__cell runs-table__proof">
                <span title={proof_grade_words(entry.proof_grade)}>{entry.proof_grade}</span>
                <small>participant-attested</small>
                <small>not independently reproduced</small>
              </div>
              <div class="runs-table__cell runs-table__published">
                <time
                  datetime={DateTime.to_iso8601(entry.accepted_at)}
                  title={arrived(entry.accepted_at)}
                >
                  {compact_arrived(entry.accepted_at)}
                </time>
              </div>
            </li>
          </ol>
        </div>

        <p :if={@next_before_sequence} class="runs-index__pagination">
          <a class="text-link" href={older_url(@next_before_sequence)}>
            Proofs published earlier <span aria-hidden="true">→</span>
          </a>
        </p>

        <p :if={@entries != []} class="runs-index__provenance small quiet">
          The first entries are Techtree’s own certification proofs. They use the same format,
          checks, and ordering as every other published proof.
        </p>

        <p class="runs-index__footer small quiet">
          <a href={~p"/proofs"}>How verification works</a>
          · <a href={~p"/climbs"}>The Climbs behind these proofs</a>
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

  defp older_url(sequence), do: "/results?before_sequence=" <> Integer.to_string(sequence)

  defp uplift_value(entry) do
    if normalized_score?(entry.baseline_mean) and normalized_score?(entry.candidate_mean) do
      uplift_percent(entry.absolute_delta)
    else
      signed_delta(entry.absolute_delta)
    end
  end

  defp uplift_percent(delta) do
    percent = Float.round(delta * 100, 1)

    if percent > 0, do: "+#{percent}%", else: "#{percent}%"
  end

  defp signed_delta(delta) do
    rounded = Float.round(delta, 3)

    if rounded > 0, do: "+#{rounded}", else: to_string(rounded)
  end

  defp normalized_score?(score), do: score >= 0 and score <= 1

  defp uplift_words(entry), do: "#{uplift_value(entry)} score uplift"

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
