defmodule TechtreeWeb.RunsLive.Show do
  @moduledoc """
  One published run, task by task, with the coordinates it was pinned to and
  the checks this site ran on it.

  The point of the page is that a reader can get from the headline number to
  the thing it was computed from without being asked to believe anything in
  between. Every task both runs attempted is here with both rewards and the
  difference, in the order the campaign committed to before either run started.
  The coordinates come from the campaign this site publishes rather than from
  the submission, so a run cannot describe the comparison it was in.

  What the page does **not** offer is the submitted bytes. Those are stored,
  immutably, and every field here was derived from them — but an address
  returning the path-to-base64 file mapping hands over the whole bundle however
  it is wrapped, and decision 0038 defers that. The bundle a reader can
  check offline is the one the participant still holds, and the command that
  checks it is on the page.

  The list of checks is the ingest's own list, read from the module that runs
  them, so a page cannot claim a check that does not exist and cannot fall
  behind one that was added.

  A withdrawn entry keeps its address and keeps its page. Withdrawal is an
  appended event rather than a deletion, so the row is still there, the address
  still resolves, and the page says at the top of it that the participant
  withdrew it and when. Copies other people hold are theirs, and this page does
  not pretend otherwise.
  """

  use TechtreeWeb, :live_view

  alias Techtree.Catalog.Query, as: Catalog
  alias Techtree.Network.Query
  alias TechtreeWeb.CampaignFacts
  alias TechtreeWeb.ClimbCopy

  @impl true
  def mount(%{"bundle_digest" => digest}, _session, socket) do
    case Query.get_entry(digest) do
      {:ok, entry} ->
        {:ok, assign(socket, assigns_for(entry))}

      :error ->
        raise TechtreeWeb.NotFoundError, "no run is published under that fingerprint"
    end
  end

  @impl true
  def handle_event("filter_tasks", %{"filter" => filter}, socket) do
    task_filter =
      if filter in ~w(all better same worse), do: String.to_existing_atom(filter), else: :all

    {:noreply, assign(socket, task_filter: task_filter)}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page wide>
      <p class="back-link"><a href={~p"/results"}>← Published proofs</a></p>

      <.warning_callout :if={@withdrawn?} title="Withdrawn by the participant">
        <p>
          {withdrawn_words(@entry.withdrawn_at)}. It was published here and the
          participant has since asked for it to be marked withdrawn. Nothing about it was
          deleted — a withdrawal is recorded, not applied — and copies anybody already
          holds are still theirs to check.
        </p>
      </.warning_callout>

      <header class="page-heading">
        <div>
          <p class="eyebrow">{@campaign_name} · {arrived(@entry.accepted_at)}</p>
          <h1 id="run-comparison">{@skill_name} vs No Skill</h1>
          <p id="run-outcome" class="lede">
            <strong>{result_difference(@entry)}</strong>
            score difference · {@entry.wins} better, {@entry.ties} same, {@entry.losses} worse.
          </p>
          <a
            :if={@github_url}
            id="run-github"
            class="github-link"
            href={@github_url}
            target="_blank"
            rel="noopener noreferrer"
          >
            <svg viewBox="0 0 16 16" aria-hidden="true">
              <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82A7.65 7.65 0 0 1 8 4.36c.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z" />
            </svg>
            View this Skill on GitHub
          </a>
        </div>
      </header>

      <section class="section">
        <p class="eyebrow">The proof</p>
        <h2>What the signed summary says</h2>
        <.definition_list>
          <:fact term="Without the Skill">{result_score(@entry.baseline_mean)}</:fact>
          <:fact term="With the Skill">{result_score(@entry.candidate_mean)}</:fact>
          <:fact term="Difference">{result_difference(@entry)}</:fact>
          <:fact term="Conclusion">{@entry.decision}</:fact>
          <:fact term="Changed Skill">
            <.digest value={@entry.skill_digest} />
          </:fact>
          <:fact term="What it may be presented as">
            {proof_grade_words(@entry.proof_grade)}
          </:fact>
        </.definition_list>
      </section>

      <section class="section">
        <p class="eyebrow">Held fixed before either run</p>
        <h2>Comparison conditions</h2>
        <.definition_list>
          <:fact term="Climb">
            <a :if={@slug} href={~p"/climbs/#{@slug}"}>{@title}</a>
            <span :if={is_nil(@slug)}>{@entry.climb_reference}</span>
          </:fact>
          <:fact term="Tasks">
            {comparison_membership_words(@published.membership)}
          </:fact>
          <:fact term="Ceiling">
            {CampaignFacts.budget_words(@published.budget) || "Not published"}
          </:fact>
          <:fact term="Agent host">
            {@entry.subject_harness} {@entry.subject_harness_version}
          </:fact>
        </.definition_list>

        <details class="integrity-details">
          <summary>Integrity details</summary>
          <.definition_list>
            <:fact term="Climb fingerprint">
              <.digest
                value={@entry.campaign_spec_digest}
                href={object_url(@entry.campaign_spec_digest)}
              />
            </:fact>
            <:fact term="Task list fingerprint">
              <.digest value={@published.membership["membership_digest"] || "Not published"} />
            </:fact>
            <:fact term="Terms fingerprint">
              <.digest
                value={@entry.data_policy_digest}
                href={object_url(@entry.data_policy_digest)}
              />
            </:fact>
            <:fact term="Model">{@entry.subject_model} · {@entry.subject_provider}</:fact>
            <:fact term="Result ID">{@entry.run_id}</:fact>
            <:fact term="Log sequence">{@entry.log_sequence}</:fact>
            <:fact term="Publisher key"><.digest value={@entry.participant_key_id} /></:fact>
          </.definition_list>
        </details>
      </section>

      <section class="section">
        <p class="eyebrow">
          {@entry.verification_checks_run} checks passed
        </p>
        <h2>Bundle verification passed.</h2>
        <p>
          The published bundle passed every required check.
          <a href={~p"/proofs"}>How verification works.</a>
        </p>
      </section>

      <section class="section">
        <p class="eyebrow">{@entry.task_count} tasks</p>
        <h2>Task by task</h2>
        <div class="tasks__filters" aria-label="Filter task outcomes">
          <button
            :for={{filter, label, count} <- task_filters(@entry)}
            type="button"
            class="tasks__filter"
            aria-pressed={to_string(@task_filter == filter)}
            phx-click="filter_tasks"
            phx-value-filter={filter}
          >
            {label} {count}
          </button>
        </div>
        <div class="tasks">
          <p class="tasks__row tasks__head" aria-hidden="true">
            <span>Task</span>
            <span class="tasks__number">Without</span>
            <span class="tasks__number">With</span>
            <span class="tasks__number">Change</span>
          </p>
          <ol>
            <li :for={task <- filtered_tasks(@tasks, @task_filter)} class="tasks__row">
              <span class="tasks__task">{task.hash}</span>
              <span class="tasks__number">
                <span class="offscreen">Without the Skill</span>{task.baseline}
              </span>
              <span class="tasks__number">
                <span class="offscreen">With the Skill</span>{task.candidate}
              </span>
              <span class="tasks__number">
                <span class="offscreen">Change</span>{task.delta}
              </span>
            </li>
          </ol>
        </div>
      </section>

      <section class="offline-verify">
        <div>
          <p class="eyebrow">Check it yourself</p>
          <h2>Verify this proof offline.</h2>
          <p class="small quiet">
            <a href={"/api/v1/publications/" <> @entry.bundle_digest}>View the recorded data</a>
            or run the verifier against the participant’s bundle.
          </p>
        </div>
        <.command_block
          id="copy-runs-verify"
          argv={["techtree", "proof", "verify", @entry.run_id]}
          label="Verify offline"
        />
      </section>

      <p class="small quiet section">
        <a href={~p"/results"}>Every published proof</a>
        · <a href={~p"/proofs"}>How verification works</a>
      </p>
    </Layouts.page>
    """
  end

  defp assigns_for(entry) do
    climb =
      case Catalog.get_climb_by_campaign_digest(entry.campaign_spec_digest) do
        {:ok, found} -> found
        {:error, _reason} -> nil
      end

    %{
      page_title: "A published proof",
      entry: entry,
      campaign_name: campaign_name(entry, climb),
      skill_name: skill_name(entry, climb),
      github_url: github_url(entry),
      withdrawn?: Query.withdrawn?(entry),
      tasks: Enum.map(entry.task_deltas, &task_row/1),
      task_filter: :all,
      published: CampaignFacts.for_climb(climb),
      slug: climb && climb.projection["slug"],
      title: campaign_name(entry, climb)
    }
  end

  defp campaign_name(entry, climb) do
    copy = climb && ClimbCopy.for_reference(climb.reference)

    present(Map.get(entry, :campaign_name)) ||
      (copy && copy.campaign_title) ||
      (climb && climb.title) ||
      entry.climb_reference
  end

  defp skill_name(entry, climb) do
    copy = climb && ClimbCopy.for_reference(climb.reference)

    present(Map.get(entry, :skill_name)) ||
      (copy && copy.candidate_skill_label) ||
      "the candidate Skill"
  end

  defp github_url(entry) do
    case Map.get(entry, :skill_github_url) do
      "https://github.com/" <> _ = url -> url
      _other -> nil
    end
  end

  defp present(value) when is_binary(value) do
    if String.trim(value) == "", do: nil, else: value
  end

  defp present(_value), do: nil

  # A digest carries a colon, which the route sigil would escape into an
  # address a reader could not compare against the one they hold.
  defp object_url(digest), do: "/api/v1/objects/" <> digest

  defp task_row(delta) do
    baseline = delta["baseline_reward"]
    candidate = delta["candidate_reward"]

    %{
      hash: delta["task_hash"],
      baseline: result_score(baseline),
      candidate: result_score(candidate),
      delta: human_difference(candidate - baseline, baseline, candidate),
      outcome: task_outcome(candidate, baseline)
    }
  end

  defp task_outcome(candidate, baseline) when candidate > baseline, do: :better
  defp task_outcome(candidate, baseline) when candidate < baseline, do: :worse
  defp task_outcome(_candidate, _baseline), do: :same

  defp filtered_tasks(tasks, :all), do: tasks
  defp filtered_tasks(tasks, outcome), do: Enum.filter(tasks, &(&1.outcome == outcome))

  defp task_filters(entry) do
    [
      {:all, "All", entry.task_count},
      {:better, "Better", entry.wins},
      {:same, "Same", entry.ties},
      {:worse, "Worse", entry.losses}
    ]
  end

  defp comparison_membership_words(membership) do
    membership
    |> CampaignFacts.membership_words()
    |> case do
      nil -> "Not published"
      words -> String.replace(words, "Test", "run")
    end
  end

  defp number(value) when is_integer(value), do: to_string(value)
  defp number(value) when is_float(value), do: value |> Float.round(3) |> to_string()

  defp signed(value) do
    rounded = value |> Kernel./(1) |> Float.round(3)

    if rounded > 0, do: "+#{rounded}", else: to_string(rounded)
  end

  defp result_score(value) when value >= 0 and value <= 1,
    do: "#{Float.round(value * 100.0, 1)}%"

  defp result_score(value), do: number(value)

  defp result_difference(entry) do
    human_difference(entry.absolute_delta, entry.baseline_mean, entry.candidate_mean)
  end

  defp human_difference(delta, baseline, candidate)
       when baseline >= 0 and baseline <= 1 and candidate >= 0 and candidate <= 1 do
    percent = Float.round(delta * 100.0, 1)
    if percent > 0, do: "+#{percent}%", else: "#{percent}%"
  end

  defp human_difference(delta, _baseline, _candidate), do: signed(delta)

  defp arrived(at) do
    at
    |> DateTime.truncate(:second)
    |> Calendar.strftime("%Y-%m-%d %H:%M UTC")
  end

  defp withdrawn_words(at) do
    "Withdrawn by the participant on " <> Calendar.strftime(at, "%-d %B %Y")
  end
end
