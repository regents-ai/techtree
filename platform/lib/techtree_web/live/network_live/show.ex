defmodule TechtreeWeb.NetworkLive.Show do
  @moduledoc """
  One published run, task by task, with the coordinates it was pinned to and
  the checks this site ran on it.

  The point of the page is that a reader can get from the headline number to
  the thing it was computed from without being asked to believe anything in
  between. Every task both runs attempted is here with both rewards and the
  difference, in the order the campaign committed to before either run started.
  The coordinates come from the campaign this site publishes rather than from
  the submission, so a run cannot describe the comparison it was in. And the
  exact bytes are one link away, so the reader can redo every check on their
  own machine.

  The list of checks is the ingest's own list, read from the module that runs
  them, so a page cannot claim a check that does not exist and cannot fall
  behind one that was added.

  A withdrawn entry keeps its address and shows nothing. Withdrawal is an
  appended event rather than a deletion, so the row is still there and the
  address still resolves; what changes is that this site stops presenting it.
  Copies other people hold are theirs, and this page does not pretend
  otherwise.
  """

  use TechtreeWeb, :live_view

  alias Techtree.Catalog.Query, as: Catalog
  alias Techtree.Network.Bundle
  alias Techtree.Network.Query
  alias TechtreeWeb.CampaignFacts

  @impl true
  def mount(%{"digest" => digest}, _session, socket) do
    case Query.get_entry(digest) do
      {:ok, entry} ->
        {:ok, assign(socket, assigns_for(entry))}

      :error ->
        raise TechtreeWeb.NotFoundError, "no run is published under that fingerprint"
    end
  end

  @impl true
  def render(%{withdrawn?: true} = assigns) do
    ~H"""
    <Layouts.page>
      <p class="back-link"><a href={~p"/network"}>← Published runs</a></p>
      <header class="page-heading">
        <p class="eyebrow">Withdrawn</p>
        <h1>This run was withdrawn</h1>
        <p class="lede">
          It was published here and is no longer shown. Nothing about it was deleted —
          a withdrawal is recorded, not applied — and copies anybody already holds are
          still theirs to check.
        </p>
      </header>
    </Layouts.page>
    """
  end

  def render(assigns) do
    ~H"""
    <Layouts.page wide>
      <p class="back-link"><a href={~p"/network"}>← Published runs</a></p>

      <header class="page-heading page-heading--split">
        <div>
          <p class="eyebrow">Published run · {arrived(@entry.inserted_at)}</p>
          <h1>{@entry.subject_harness} {@entry.subject_harness_version} on {@entry.subject_model}</h1>
          <p class="lede">
            {@entry.wins} of {@entry.task_count} tasks came out better with the Skill, {@entry.ties} came out the same, and {@entry.losses} came out worse.
          </p>
        </div>
        <.digest value={@entry.executor_key_id} />
      </header>

      <section class="section">
        <p class="eyebrow">The result</p>
        <h2>What the signed summary says</h2>
        <.definition_list>
          <:fact term="Without the Skill">{number(@entry.baseline_mean)}</:fact>
          <:fact term="With the Skill">{number(@entry.candidate_mean)}</:fact>
          <:fact term="Difference">{signed(@entry.absolute_delta)}</:fact>
          <:fact term="Conclusion">{@entry.decision}</:fact>
          <:fact term="What it may be presented as">
            {proof_grade_words(@entry.proof_grade)}
          </:fact>
        </.definition_list>
      </section>

      <section class="section">
        <p class="eyebrow">Held fixed before either run</p>
        <h2>The coordinates this run pins</h2>
        <.definition_list>
          <:fact term="Campaign">
            <a :if={@slug} href={~p"/campaigns/#{@slug}"}>{@title}</a>
            <span :if={is_nil(@slug)}>{@entry.climb_reference}</span>
          </:fact>
          <:fact term="Campaign fingerprint">
            <.digest
              value={@entry.campaign_spec_digest}
              href={object_url(@entry.campaign_spec_digest)}
            />
          </:fact>
          <:fact term="Tasks">
            {CampaignFacts.membership_words(@published.membership) || "Not published"}
          </:fact>
          <:fact term="Task list fingerprint">
            <.digest value={@published.membership["membership_digest"] || "Not published"} />
          </:fact>
          <:fact term="Ceiling">
            {CampaignFacts.budget_words(@published.budget) || "Not published"}
          </:fact>
          <:fact term="Terms">
            <.digest
              value={@entry.data_policy_digest}
              href={object_url(@entry.data_policy_digest)}
            />
          </:fact>
          <:fact term="Run">{@entry.run_id}</:fact>
        </.definition_list>
      </section>

      <section class="section">
        <p class="eyebrow">
          {@entry.verification_checks_passed} of {@entry.verification_checks_run} passed
        </p>
        <h2>What this site checked</h2>
        <ul class="checks">
          <li :for={{_name, sentence} <- @checks}>
            <span class="checks__mark" aria-hidden="true">✓</span>
            <span>{sentence}</span>
          </li>
        </ul>
        <p class="small quiet">
          Every one of those is a property of the bytes, and every one of them passed —
          a receipt that does not pass all of them is never published here. None of them
          is a claim that the run happened. This site did not watch it and has not
          repeated it, so it remains the participant's own account of their own machine.
        </p>
      </section>

      <section class="section">
        <p class="eyebrow">{@entry.task_count} tasks</p>
        <h2>Task by task</h2>
        <div class="tasks">
          <p class="tasks__row tasks__head" aria-hidden="true">
            <span>Task</span>
            <span class="tasks__number">Without</span>
            <span class="tasks__number">With</span>
            <span class="tasks__number">Change</span>
          </p>
          <ol>
            <li :for={task <- @tasks} class="tasks__row">
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
          <h2>The exact bytes this site was given.</h2>
          <p class="small quiet">
            Everything above was computed from these and nothing else, so the whole of it
            can be redone on your own machine without asking this site for anything: <a href={"/api/v1/submissions/" <> @entry.bundle_digest}>fetch the receipt</a>.
          </p>
        </div>
        <.command_block
          id="copy-network-verify"
          argv={["techtree", "proof", "verify", "path/to/result-bundle"]}
          label="Verify offline"
        />
      </section>

      <p class="small quiet section">
        <a href={~p"/network"}>Every published run</a>
        · <a href={~p"/proofs"}>What a finished comparison contains</a>
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
      page_title: "A published run",
      entry: entry,
      withdrawn?: Query.withdrawn?(entry),
      checks: Bundle.checks(),
      tasks: Enum.map(entry.task_deltas, &task_row/1),
      published: CampaignFacts.for_climb(climb),
      slug: climb && climb.projection["slug"],
      title: (climb && climb.title) || entry.climb_reference
    }
  end

  # A digest carries a colon, which the route sigil would escape into an
  # address a reader could not compare against the one they hold.
  defp object_url(digest), do: "/api/v1/objects/" <> digest

  defp task_row(delta) do
    %{
      hash: delta["task_hash"],
      baseline: number(delta["baseline_reward"]),
      candidate: number(delta["candidate_reward"]),
      delta: signed(delta["candidate_reward"] - delta["baseline_reward"])
    }
  end

  defp number(value) when is_integer(value), do: to_string(value)
  defp number(value) when is_float(value), do: value |> Float.round(3) |> to_string()

  defp signed(value) do
    rounded = value |> Kernel./(1) |> Float.round(3)

    if rounded > 0, do: "+#{rounded}", else: to_string(rounded)
  end

  defp arrived(at) do
    at
    |> DateTime.truncate(:second)
    |> Calendar.strftime("%Y-%m-%d %H:%M UTC")
  end
end
