defmodule TechtreeWeb.RunsLive.Show do
  @moduledoc """
  One published Result, laid out to answer one question: should I keep this
  Skill change?

  The answer comes first, in words, with the tasks that went each way. Then a
  few tasks side by side, the exact change the signed report found between the
  two runs, what stands behind the numbers, and how to run the comparison
  again. The full task list and the fingerprints sit underneath, folded, so a
  narrow screen reads the answer before the evidence.

  The verdict, the means and the counts are this site's own: the Result's
  stored `Techtree.Network.Assessment`, which `Techtree.Network.Result` worked
  out under its Campaign's rule when the Result was published.
  `TechtreeWeb.ResultAssessment` puts that into words. The standing gap is a
  rerun by anybody else: this site keeps no record of one, so the page never
  claims one.

  What this page does **not** offer is the submitted bytes. Those are stored
  immutably, every field here was derived from them, and they have an address
  of their own on the API rather than a control on this page.

  A withdrawn entry keeps its address and keeps its page. Withdrawal is an
  appended event rather than a deletion, so the page says at the top of it
  that the participant withdrew it and when.
  """

  use TechtreeWeb, :live_view

  alias Techtree.Catalog.Query, as: Catalog
  alias Techtree.Network.Query
  alias TechtreeWeb.CampaignFacts
  alias TechtreeWeb.ClimbCopy
  alias TechtreeWeb.Providers
  alias TechtreeWeb.ReleaseInfo
  alias TechtreeWeb.ResultAssessment

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
    assigns = assign(assigns, :filtered_tasks, filtered_tasks(assigns.tasks, assigns.task_filter))

    ~H"""
    <Layouts.page wide>
      <p class="back-link"><a href={~p"/results"}>← Published Results</a></p>

      <.warning_callout :if={@withdrawn?} title="Withdrawn by the participant">
        <p>
          {withdrawn_words(@entry.withdrawn_at)}. It was published here and the
          participant has since asked for it to be marked withdrawn. Nothing about it was
          deleted — a withdrawal is recorded, not applied — and copies anybody already
          holds are still theirs to check.
        </p>
      </.warning_callout>

      <header class="page-heading">
        <p class="eyebrow">{@campaign_name} · {arrived(@entry.accepted_at)}</p>
        <h1 id="run-comparison">{@skill_name} vs No Skill</h1>
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
      </header>

      <section
        id="run-assessment"
        class={["assessment", "assessment--#{ResultAssessment.verdict(@assessment)}"]}
        aria-labelledby="run-verdict"
      >
        <h2 id="run-verdict" class="assessment__verdict">
          <span class="eyebrow">Keep this Skill change?</span>
          <span>{ResultAssessment.verdict_label(@assessment)}</span>
        </h2>
        <p class="assessment__reason">{ResultAssessment.reason(@assessment)}</p>
        <p id="run-outcome" class="assessment__outcome">
          <strong>{ResultAssessment.mean_change(@assessment)}</strong>
          · {@assessment.wins} better, {@assessment.ties} same, {@assessment.losses} worse.
        </p>
        <p class="assessment__means">
          Without the Skill {ResultAssessment.mean(@assessment, :baseline)} · With the Skill {ResultAssessment.mean(
            @assessment,
            :candidate
          )}
        </p>
        <ul class="assessment__tasks">
          <li :for={outcome <- [:better, :worse, :same]} id={"tasks-#{outcome}"}>
            <strong>{task_group_words(outcome, length(@groups[outcome]))}</strong>
            <span :if={outcome != :same and @groups[outcome] != []}>
              {Enum.map_join(@groups[outcome], ", ", & &1.label)}
            </span>
          </li>
        </ul>
      </section>

      <section id="run-examples" class="section">
        <p class="eyebrow">Examples</p>
        <h2>Tasks with and without the Skill</h2>
        <p class="small quiet section-note">
          A published Result keeps each task's fingerprint and score. It does not keep the
          task's words or the agent's answers, so these examples show scores only.
        </p>
        <ul class="task-examples">
          <li :for={task <- @examples} id={"example-#{task.outcome}"} class="task-example">
            <p class="task-example__head">
              <strong>{task.label}</strong>
              <span class={["task-example__outcome", "task-example__outcome--#{task.outcome}"]}>
                {outcome_label(task.outcome)}
              </span>
            </p>
            <code title={task.hash}>{task.short_hash}</code>
            <dl class="task-example__scores">
              <div>
                <dt>Without the Skill</dt>
                <dd>{task.baseline}</dd>
              </div>
              <div>
                <dt>With the Skill</dt>
                <dd>{task.candidate}</dd>
              </div>
              <div>
                <dt>Change</dt>
                <dd>{task.delta}</dd>
              </div>
            </dl>
          </li>
        </ul>
      </section>

      <section id="run-skill-change" class="section">
        <p class="eyebrow">The Skill change</p>
        <h2>What differed between the two runs</h2>
        <p class="section-note">
          The signed report compared the settings of the two runs and found only this
          difference, which is the one the Climb allows.
        </p>
        <ul class="skill-change">
          <li :for={change <- @assessment.skill_changes} class="skill-change__item">
            <p><strong>{ResultAssessment.change_label(change, @one_skill?)}</strong></p>
            <.definition_list>
              <:fact term="Without the Skill"><.change_value value={change.without} /></:fact>
              <:fact term="With the Skill"><.change_value value={change.with} /></:fact>
            </.definition_list>
          </li>
        </ul>
        <p :if={@assessment.model_build_unproven} id="run-model-build" class="section-note">
          {Providers.name!(@entry.subject_provider)} does not publish a build number for {@entry.subject_model}, so both runs are known to have asked for the same model name, not shown to have used the same build of it.
        </p>
        <p class="small quiet section-note">
          The signed report names the Skill by its fingerprint, not by the name this page
          shows for it.
        </p>
      </section>

      <section id="run-evidence" class="section">
        <p class="eyebrow">Evidence</p>
        <h2>What stands behind these numbers</h2>
        <ul class="evidence-badges">
          <li id="badge-files-verified" class="evidence-badge">
            <Regent.Primitives.status tone="success" class="badge">
              Files verified
            </Regent.Primitives.status>
            <p>
              This site ran its {@entry.verification_checks_run} checks on the Result's files, including one that worked out the averages, the change and the decision again from the task scores, and every check passed.
              <a href={~p"/proofs"}>How verification works.</a>
            </p>
          </li>
          <li id="badge-reported" class="evidence-badge">
            <Regent.Primitives.status tone="neutral" class="badge">
              Reported by the person who ran it
            </Regent.Primitives.status>
            <p>
              The numbers are signed with the key of the person who ran both runs on their own
              machine. Nobody else watched the runs.
            </p>
          </li>
          <li id="badge-not-reproduced" class="evidence-badge">
            <Regent.Primitives.status tone="neutral" class="badge">
              Not yet reproduced
            </Regent.Primitives.status>
            <p>This site has no record of anybody else running this comparison again.</p>
          </li>
        </ul>
      </section>

      <section id="run-rerun" class="section">
        <p class="eyebrow">Check it yourself</p>
        <h2>Run this comparison again</h2>
        <div :if={match?(%{}, @rerun)} class="rerun">
          <div class="rerun__needs">
            <h3>You need</h3>
            <.requirements minimums={@rerun.minimums} provider={false} hermes={false}>
              <li>
                An API key for {@limits.provider}, set as <code>{@limits.credential_env}</code>; the model calls are charged to your account
              </li>
              <li :if={@github_url}>
                The Skill's files, from
                <a href={@github_url} target="_blank" rel="noopener noreferrer">its GitHub page</a>
              </li>
              <li :if={!@github_url}>
                The Skill's files. This Result does not say where to get them.
              </li>
            </.requirements>
          </div>
          <.command_block id="copy-run-rerun" label="Run it again" lines={@rerun.commands} />
        </div>
        <p :if={@rerun == :no_release} class="section-note">
          This site is not serving a release you can install right now, so there are no
          commands to show.
        </p>
        <p :if={@rerun == :climb_retired} class="section-note">
          The release this site serves now no longer includes this Result's Climb, so it
          cannot run this comparison again.
        </p>

        <h3 class="rerun__heading">Limits</h3>
        <.definition_list>
          <:fact term="Each try">
            Stops starting model calls at {@limits.calls} calls, {@limits.input_tokens} input tokens or {@limits.output_tokens} output tokens, whichever comes first.
          </:fact>
          <:fact term="Whole run">
            {@limits.plan}: up to {@limits.tries} tries. At most {@limits.run_calls} model calls. The token limits add up to {@limits.run_input_tokens} input tokens and {@limits.run_output_tokens} output tokens.
          </:fact>
          <:fact term="Before it starts">
            Techtree shows the most the run may spend and waits for your yes.
          </:fact>
        </.definition_list>
        <p class="small quiet section-note">
          The call that crosses a limit still finishes, so a try can go past its token limits
          by up to one full request and its reply.
        </p>

        <h3 class="rerun__heading">What a new run can tell you</h3>
        <ul class="needs">
          <li>
            A new run is a new Result. The model may not answer the same way twice, so its
            numbers can differ from these.
          </li>
          <li>
            Whether yours agrees is for you to judge. This site keeps no record that ties a new
            run to this Result.
          </li>
        </ul>
      </section>

      <section class="section">
        <p class="eyebrow">The evidence in full</p>
        <h2>Every task and every fingerprint</h2>

        <Regent.Primitives.disclosure
          id="run-all-tasks"
          summary={"All #{@entry.task_count} tasks"}
          index="01"
          class="integrity-details"
          phx-mounted={JS.ignore_attributes(["open"])}
        >
          <div class="tasks__filters" aria-label="Filter task outcomes">
            <Regent.Primitives.button
              :for={{filter, label, count} <- task_filters(@entry, @assessment)}
              variant="secondary"
              id={"task-filter-#{filter}"}
              type="button"
              class="tasks__filter"
              aria-pressed={to_string(@task_filter == filter)}
              phx-click="filter_tasks"
              phx-value-filter={filter}
            >
              {label} {count}
            </Regent.Primitives.button>
          </div>
          <p id="task-filter-status" class="offscreen" aria-live="polite">
            {filter_status(@task_filter, length(@filtered_tasks))}
          </p>
          <div
            id="task-results"
            class="tasks"
            role="region"
            aria-label="Task results, scroll sideways for all scores"
            tabindex="0"
          >
            <p class="tasks__row tasks__head" aria-hidden="true">
              <span>Task</span>
              <span class="tasks__number">Without</span>
              <span class="tasks__number">With</span>
              <span class="tasks__number">Change</span>
            </p>
            <p :if={@filtered_tasks == []} class="empty-state tasks__empty">
              {empty_filter_words(@task_filter)}
            </p>
            <ol>
              <li :for={task <- @filtered_tasks} class="tasks__row">
                <span class="tasks__task" title={task.hash}>
                  <strong>{task.label}</strong>
                  <code>{task.short_hash}</code>
                </span>
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
        </Regent.Primitives.disclosure>

        <Regent.Primitives.disclosure
          id="run-integrity-details"
          summary="Comparison conditions and fingerprints"
          index="02"
          class="integrity-details"
        >
          <.definition_list>
            <:fact term="Climb">
              <a :if={@slug} href={~p"/climbs/#{@slug}"}>{@campaign_name}</a>
              <span :if={is_nil(@slug)}>{@entry.climb_reference}</span>
            </:fact>
            <:fact term="Tasks">
              {comparison_membership_words(@published.membership)}
            </:fact>
            <:fact term="Agent host">
              {@entry.subject_harness} {@entry.subject_harness_version}
            </:fact>
            <:fact term="Model">
              {@entry.subject_model} from {Providers.name!(@entry.subject_provider)}
            </:fact>
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
            <:fact term="Result ID">{@entry.run_id}</:fact>
            <:fact term="Log sequence">{@entry.log_sequence}</:fact>
            <:fact term="What the report can claim">
              A call, signed by the person who ran it. Not repeated by anybody else.
            </:fact>
            <:fact term="Publisher key"><.digest value={@entry.participant_key_id} /></:fact>
          </.definition_list>
        </Regent.Primitives.disclosure>
      </section>

      <section class="offline-verify">
        <div>
          <p class="eyebrow">Check this copy</p>
          <h2>Verify this Result offline.</h2>
          <p class="small quiet">
            <a href={"/api/v1/publications/" <> @entry.bundle_digest}>View the recorded data</a>
            or run the verifier against a copy of the participant’s Result bundle.
          </p>
        </div>
        <.command_block
          id="copy-runs-verify"
          argv={["techtree", "proof", "verify", "path/to/result-bundle"]}
          label="Verify offline"
        />
      </section>

      <p class="small quiet section">
        <a href={~p"/results"}>All Results</a> · <a href={~p"/proofs"}>How verification works</a>
      </p>
    </Layouts.page>
    """
  end

  attr :value, :any, required: true

  defp change_value(%{value: %{kind: :none}} = assigns), do: ~H"No Skill"
  defp change_value(%{value: %{kind: :not_set}} = assigns), do: ~H"Not set"

  defp change_value(%{value: %{kind: :skill}} = assigns) do
    ~H"""
    <.digest value={@value.digest} />
    <span class="small quiet">{CampaignFacts.count(@value.size)} bytes</span>
    """
  end

  defp change_value(%{value: %{kind: :digest}} = assigns),
    do: ~H"<.digest value={@value.digest} />"

  defp change_value(%{value: %{kind: :size}} = assigns),
    do: ~H"{CampaignFacts.count(@value.size)} bytes"

  defp change_value(%{value: %{kind: :text}} = assigns), do: ~H"<code>{@value.text}</code>"

  # Ingest only publishes a Result whose Campaign this site publishes, and
  # stores its assessment with it, and a Climb is retired rather than removed,
  # so each of these holds for every published Result.
  defp assigns_for(entry) do
    {:ok, climb} = Catalog.get_any_climb_by_campaign_digest(entry.campaign_spec_digest)
    campaign = CampaignFacts.campaign!(climb)

    skill_name = skill_name(entry, climb)
    tasks = ResultAssessment.tasks(entry.task_deltas)
    groups = ResultAssessment.by_outcome(tasks)

    %{
      page_title: "#{skill_name} vs No Skill",
      entry: entry,
      campaign_name: campaign_name(entry, climb),
      skill_name: skill_name,
      github_url: github_url(entry),
      withdrawn?: Query.withdrawn?(entry),
      assessment: entry.assessment,
      groups: groups,
      examples: ResultAssessment.examples(groups),
      one_skill?: campaign["mutation_contract"]["maximum_skills"] == 1,
      tasks: tasks,
      task_filter: :all,
      published: CampaignFacts.for_climb(climb),
      limits: limits(campaign),
      rerun: rerun(entry),
      slug: climb.projection["slug"]
    }
  end

  # The limits the Result's own Campaign set, per try and over the whole run.
  defp limits(campaign) do
    trial = CampaignFacts.trial(campaign)
    total = CampaignFacts.run_total(trial)

    %{
      provider: Providers.name!(trial.provider),
      credential_env: trial.credential_env,
      plan: plan_words(trial),
      calls: CampaignFacts.count(trial.calls),
      input_tokens: CampaignFacts.count(trial.input_tokens),
      output_tokens: CampaignFacts.count(trial.output_tokens),
      tries: CampaignFacts.count(total.tries),
      run_calls: CampaignFacts.count(total.calls),
      run_input_tokens: CampaignFacts.count(total.input_tokens),
      run_output_tokens: CampaignFacts.count(total.output_tokens)
    }
  end

  # How many tries the whole run is made of, in words.
  defp plan_words(trial) do
    times =
      case trial.rollouts do
        1 -> "once"
        rollouts -> "#{rollouts} times"
      end

    retries =
      case trial.retries do
        0 -> ""
        1 -> ", with up to 1 more attempt for a try that fails"
        retries -> ", with up to #{retries} more attempts for a try that fails"
      end

    "#{CampaignFacts.count(trial.tasks)} tasks, each tried #{times} without the Skill and " <>
      "#{times} with it#{retries}"
  end

  # The commands only exist when the release served now installs and still
  # carries this Result's Climb; a retired Climb cannot be run by it.
  defp rerun(entry) do
    case ReleaseInfo.current() do
      %{installable?: true, install_argv: [_ | _] = install_argv, minimums: minimums} ->
        case Catalog.get_climb_by_campaign_digest(entry.campaign_spec_digest) do
          {:ok, climb} ->
            %{
              minimums: minimums,
              commands: rerun_commands(install_argv, climb.reference, entry.skill_digest)
            }

          {:error, _retired} ->
            :climb_retired
        end

      _not_installable ->
        :no_release
    end
  end

  defp rerun_commands(install_argv, reference, fingerprint) do
    [
      {:command, install_argv},
      {:command, ["techtree", "setup"]},
      {:command, ["techtree", "doctor", "--climb", reference]},
      {:comment, "Put the Skill's files in a folder, then prepare it:"},
      {:command, ["techtree", "climb", "prepare", reference, "--skill", "path/to/skill"]},
      {:comment, "Check that the Skill content digest it prints is #{fingerprint}"},
      {:comment, "Start the draft it names. Techtree shows the most it may spend first:"},
      {:command, ["techtree", "climb", "start", "DRAFT_ID"]},
      {:comment, "When it finishes, check the run and read its result:"},
      {:command, ["techtree", "run", "result", "RUN_ID"]}
    ]
  end

  defp campaign_name(entry, climb) do
    copy = ClimbCopy.for_reference(climb.reference)

    present(Map.get(entry, :campaign_name)) ||
      climb.title ||
      (copy && copy.campaign_title) ||
      entry.climb_reference
  end

  defp skill_name(entry, climb) do
    copy = ClimbCopy.for_reference(climb.reference)

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

  defp task_group_words(:better, count), do: "Better on #{tasks_words(count)}#{colon(count)}"
  defp task_group_words(:worse, count), do: "Worse on #{tasks_words(count)}#{colon(count)}"
  defp task_group_words(:same, count), do: "No change on #{tasks_words(count)}."

  defp tasks_words(0), do: "no tasks"
  defp tasks_words(1), do: "1 task"
  defp tasks_words(count), do: "#{count} tasks"

  defp colon(0), do: "."
  defp colon(_count), do: ":"

  defp outcome_label(:better), do: "Better with the Skill"
  defp outcome_label(:worse), do: "Worse with the Skill"
  defp outcome_label(:same), do: "No change"

  defp filtered_tasks(tasks, :all), do: tasks
  defp filtered_tasks(tasks, outcome), do: Enum.filter(tasks, &(&1.outcome == outcome))

  defp filter_status(filter, count) do
    "#{filter_label(filter)} #{count} #{if(count == 1, do: "task", else: "tasks")} shown."
  end

  defp filter_label(:all), do: "All"
  defp filter_label(:better), do: "Better"
  defp filter_label(:same), do: "Same"
  defp filter_label(:worse), do: "Worse"

  defp empty_filter_words(:better), do: "No tasks were better."
  defp empty_filter_words(:same), do: "No tasks were the same."
  defp empty_filter_words(:worse), do: "No tasks were worse."
  defp empty_filter_words(:all), do: "No tasks are available."

  defp task_filters(entry, assessment) do
    [
      {:all, "All", entry.task_count},
      {:better, "Better", assessment.wins},
      {:same, "Same", assessment.ties},
      {:worse, "Worse", assessment.losses}
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

  defp arrived(at) do
    at
    |> DateTime.truncate(:second)
    |> Calendar.strftime("%Y-%m-%d %H:%M UTC")
  end

  defp withdrawn_words(at) do
    "Withdrawn by the participant on " <> Calendar.strftime(at, "%-d %B %Y")
  end
end
