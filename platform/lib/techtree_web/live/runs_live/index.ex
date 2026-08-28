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

  @impl true
  def mount(_params, _session, socket) do
    {:ok, assign(socket, page_title: "Published runs")}
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
    <Layouts.page wide>
      <header class="page-heading">
        <p class="eyebrow">Participant-attested</p>
        <h1>Published runs</h1>
        <p class="lede">
          Every comparison somebody has chosen to publish, newest first, in the order
          they arrived. This is a record of what was sent, not a table of standings.
          There is no other order to put it in, and no way to ask for one.
        </p>
      </header>

      <.warning_callout title="What this site checked, and what it did not">
        <p>
          Each receipt below was checked here: every file hashes to what the bundle
          says it does, every signature holds under the key the bundle carries, and the
          scores add up from the task results in the same bundle. That is a receipt
          being internally consistent and signed by the key it names.
        </p>
        <p class="small quiet">
          It is not a claim that the run happened. This site did not watch it and has
          not repeated it. Every entry stays the participant's own account of their own
          machine, and anyone can redo all of it themselves from the bundle they hold.
        </p>
      </.warning_callout>

      <p :if={@entries == []} class="empty-state section">
        Nobody has published a run yet. This is where the first one will appear.
      </p>

      <div :if={@entries != []} class="log">
        <article :for={entry <- @entries} class="log__entry">
          <div class="log__head">
            <div>
              <p class="eyebrow">{entry.subject_harness} {entry.subject_harness_version}</p>
              <h2 class="log__title">{entry.subject_model}</h2>
            </div>
            <p class="log__when">{arrived(entry.accepted_at)}</p>
          </div>

          <p :if={entry.withdrawn_at} class="log__withdrawn">
            {withdrawn_words(entry.withdrawn_at)}
          </p>

          <dl class="log__facts">
            <div>
              <dt>Task by task</dt>
              <dd>{entry.wins} better · {entry.ties} same · {entry.losses} worse</dd>
            </div>
            <div>
              <dt>Difference</dt>
              <dd>{signed(entry.absolute_delta)}</dd>
            </div>
            <div>
              <dt>Grade</dt>
              <dd>{entry.proof_grade}</dd>
            </div>
            <div>
              <dt>Published by</dt>
              <dd><.digest value={fingerprint(entry.participant_key_id)} /></dd>
            </div>
          </dl>

          <a class="text-link" href={entry_url(entry)}>
            Inspect this run <span aria-hidden="true">→</span>
          </a>
        </article>
      </div>

      <p :if={@next_before_sequence} class="section">
        <a class="text-link" href={older_url(@next_before_sequence)}>
          Runs published earlier <span aria-hidden="true">→</span>
        </a>
      </p>

      <p class="small quiet section">
        <a href={~p"/proofs"}>What a finished comparison contains</a>
        · <a href={~p"/campaigns"}>The campaigns these runs are of</a>
      </p>
    </Layouts.page>
    """
  end

  # A digest carries a colon, which the route sigil would escape into an
  # address a reader could not compare against the one they hold.
  defp entry_url(entry), do: "/runs/" <> entry.bundle_digest

  defp older_url(sequence), do: "/runs?before_sequence=" <> Integer.to_string(sequence)

  # A publisher is named by the fingerprint of the key that signed their
  # bundle, shortened for reading rather than for comparing: the entry's own
  # page carries the whole of it.
  defp fingerprint("sha256:" <> hex), do: "sha256:" <> String.slice(hex, 0, 12) <> "…"
  defp fingerprint(key_id), do: key_id

  defp signed(delta) do
    rounded = Float.round(delta, 3)

    if rounded > 0, do: "+#{rounded}", else: to_string(rounded)
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
