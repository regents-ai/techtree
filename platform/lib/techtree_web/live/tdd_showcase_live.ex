defmodule TechtreeWeb.TddShowcaseLive do
  @moduledoc """
  One example comparison, laid out like a published Result's page to answer
  the same question: should I keep this Skill change?

  The answer is judged on the held-out tasks alone, the tasks kept from any
  agent that tries to improve the Skill, and comes first, in words, with the
  tasks that went each way. The tasks such an agent could see follow on their
  own. Then the claims each task tests, the Skill itself, what stands behind
  the numbers and how they were made, and how to check and run the
  comparison again from its export. The full task list, the Skill's files and
  the fingerprints sit underneath, folded.

  Everything comes from `TechtreeWeb.TddShowcase`, which reads the files the
  CLI wrote. The page shows no money: what the calls cost depends on the
  provider, and this site cannot quote it.
  """

  use TechtreeWeb, :live_view

  alias TechtreeWeb.Providers
  alias TechtreeWeb.ResultAssessment
  alias TechtreeWeb.TddShowcase

  @impl true
  def mount(_params, _session, socket) do
    showcase = TddShowcase.load!(TddShowcase.folder())

    {:ok,
     assign(socket,
       page_title: "#{showcase.skill.name} vs No Skill",
       showcase: showcase,
       export_url: TddShowcase.export_url(),
       held_out: TddShowcase.by_outcome(showcase.held_out.tasks),
       study: TddShowcase.by_outcome(showcase.study.tasks)
     )}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page wide>
      <p class="back-link"><a href={~p"/"}>← Techtree</a></p>

      <header class="page-heading">
        <p class="eyebrow">Example comparison · {date(@showcase.created_at)}</p>
        <h1 id="showcase-comparison">{@showcase.skill.name} vs No Skill</h1>
        <p class="section-note">
          A local comparison of the {@showcase.skill.name} Skill against no Skill, reported by the person who ran it.
        </p>
      </header>

      <section
        id="showcase-assessment"
        class={["assessment", "assessment--#{verdict_class(@showcase.held_out.verdict)}"]}
        aria-labelledby="showcase-verdict"
      >
        <h2 id="showcase-verdict" class="assessment__verdict">
          <span class="eyebrow">Keep this Skill change?</span>
          <span>{verdict_label(@showcase.held_out.verdict)}</span>
        </h2>
        <p class="assessment__reason">{reason(@showcase.held_out)}</p>
        <p class="assessment__outcome">
          Judged on the held-out tasks alone: tasks kept from any agent that tries to improve
          the Skill, so the answer does not rest on tasks it could learn from.
        </p>
        <.averages part={@showcase.held_out} />
        <.outcome_groups id="held-out" groups={@held_out} />
      </section>

      <section id="showcase-study" class="section">
        <p class="eyebrow">Tasks the improving agent could see</p>
        <h2 :if={@showcase.study.tasks == []}>The improving agent was shown no tasks</h2>
        <h2 :if={@showcase.study.tasks != []}>
          {verdict_label(@showcase.study.verdict)} on {other_tasks(length(@showcase.study.tasks))}
        </h2>
        <p class="section-note">
          An agent that tries to improve the Skill from this comparison is shown these tasks, so
          they are reported here on their own and do not decide the answer above.
        </p>
        <.averages part={@showcase.study} />
        <.outcome_groups :if={@showcase.study.tasks != []} id="study" groups={@study} />
      </section>

      <section id="showcase-claims" class="section">
        <p class="eyebrow">Claims</p>
        <h2>What the Skill claims, and the tasks that test it</h2>
        <p class="section-note">
          A positive case is one where following the Skill should give the right result; a
          boundary case sits at the edge of where the claim applies; a counterexample checks
          that the Skill is not overused where it would give a wrong result or should change
          nothing.
        </p>
        <div :for={claim <- @showcase.claims} id={"claim-#{claim.id}"} class="skill-change__item">
          <h3>{claim.id}. {claim.statement}</h3>
          <p class="section-note">What would show it: {claim.observable}</p>
          <ul class="task-examples">
            <li :for={task <- claim.tasks} id={"task-#{task.name}"} class="task-example">
              <p class="task-example__head">
                <strong>{task.name}</strong>
                <span class={["task-example__outcome", "task-example__outcome--#{task.outcome}"]}>
                  {outcome_label(task.outcome)}
                </span>
              </p>
              <p class="small">{task.summary}</p>
              <p class="small quiet">
                {kind_words(task.kind)} · {part_words(task.part)} · time limit {task.time_limit}
              </p>
              <.scores task={task} />
              <p :for={missing <- task.unscored} class="small quiet">
                No score {run_words(missing.run)}: {ended_words(missing.ended)}.
              </p>
            </li>
          </ul>
        </div>
      </section>

      <section id="showcase-skill" class="section">
        <p class="eyebrow">The Skill change</p>
        <h2>What differed between the two runs</h2>
        <p class="section-note">
          The two runs used the same tasks, model and limits. One ran with no Skill; the other
          ran with this Skill, the one the tasks were written from.
        </p>
        <.definition_list>
          <:fact term="Without the Skill">No Skill</:fact>
          <:fact term="With the Skill">{@showcase.skill.name}</:fact>
          <:fact term="Licence">
            {@showcase.skill.licence.name}. {@showcase.skill.licence.copyright}
          </:fact>
          <:fact term="Fingerprint"><.digest value={@showcase.skill.digest} /></:fact>
        </.definition_list>
        <p class="small quiet section-note">
          The Skill's files, its licence among them, are below, exactly as the run with the Skill
          used them. <a href="#showcase-skill-files">Read the Skill's files.</a>
        </p>
      </section>

      <section id="showcase-evidence" class="section">
        <p class="eyebrow">Evidence</p>
        <h2>What stands behind these numbers</h2>
        <ul class="evidence-badges">
          <li id="badge-files-checked" class="evidence-badge">
            <Regent.Primitives.status tone="success" class="badge">
              Files checked
            </Regent.Primitives.status>
            <p>
              This site checked the files behind this page against each other: each of the
              Skill's files and the Skill's fingerprint, both runs' records, the export's tasks
              and instructions, and the decision, worked out again from the task scores. Every
              check passed.
            </p>
          </li>
          <li id="badge-reported" class="evidence-badge">
            <Regent.Primitives.status tone="neutral" class="badge">
              Reported by the person who ran it
            </Regent.Primitives.status>
            <p>
              One local comparison, run on one computer by the person who reported it. It is not
              a published Result, nothing about it is signed, and nobody else watched the runs.
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

      <section id="showcase-method" class="section">
        <p class="eyebrow">Method</p>
        <h2>How the numbers were made</h2>
        <.definition_list>
          <:fact term="What this is">
            One local comparison on one computer. It is not a published or signed Result.
          </:fact>
          <:fact term="Tries">Each task was tried once without the Skill and once with it.</:fact>
          <:fact term="Model">{model_words(@showcase.model)}, as both runs asked for it</:fact>
          <:fact term="What limited the runs">
            {time_limit_words(@showcase.tasks)} Each try ran in its own container with {limits_words(
              @showcase.limits
            )} and no network. Nothing limited the agent's turns, model calls or tokens.
          </:fact>
          <:fact term="Model calls and tokens">
            Without the Skill {usage_words(@showcase.arms.baseline)}. With the Skill {usage_words(
              @showcase.arms.candidate
            )}.
          </:fact>
        </.definition_list>

        <h3 class="rerun__heading">What these runs cannot show</h3>
        <ul id="showcase-not-established" class="needs">
          <li :for={point <- @showcase.not_established}>{not_established_words(point)}</li>
        </ul>
      </section>

      <section id="showcase-rerun" class="section">
        <p class="eyebrow">Check it yourself</p>
        <h2>Check the tasks and run this comparison again</h2>
        <.definition_list>
          <:fact term="Fingerprint of the tasks">
            <.digest value={@showcase.fingerprint} />
          </:fact>
        </.definition_list>
        <p class="small quiet section-note">
          The first command below prints the fingerprint of the tasks it checks. They are the same
          tasks as these only if it matches this one.
        </p>
        <div class="rerun">
          <div class="rerun__needs">
            <h3>You need</h3>
            <ul class="needs">
              <li>
                <a id="showcase-export" href={@export_url}>The export folder of these tasks</a>,
                with its tests and records. Use it only if the first command prints the
                fingerprint above; a folder with any other fingerprint holds other tasks.
              </li>
              <li>The Skill's files, shown on this page, in a folder of their own</li>
              <li>Docker, Techtree and Hermes, as the export folder's own instructions describe</li>
              <li>An account with a model provider you choose; its calls may cost money</li>
            </ul>
          </div>
          <.command_block
            id="copy-showcase-rerun"
            label="Check it and run it again"
            lines={Enum.map(@showcase.commands, &{:command, &1})}
          />
        </div>
        <p class="small quiet section-note">
          Words in capitals stand for what only you know: your folders, the provider and model
          you choose, and the ids the two runs print. Each run shows what it will do and asks
          before it starts.
        </p>

        <h3 class="rerun__heading">What a new run can tell you</h3>
        <ul class="needs">
          <li>
            A new run is a new comparison. The model may not answer the same way twice, so its
            numbers can differ from these.
          </li>
          <li>
            Whether yours agrees is for you to judge. This site keeps no record that ties a new
            run to this one.
          </li>
        </ul>
      </section>

      <section class="section">
        <p class="eyebrow">The evidence in full</p>
        <h2>Every task, the Skill's files and the fingerprints</h2>

        <Regent.Primitives.disclosure
          id="showcase-all-tasks"
          summary={"All #{length(@showcase.tasks)} tasks"}
          index="01"
          class="integrity-details"
        >
          <div
            id="showcase-task-results"
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
            <ol>
              <li :for={task <- @showcase.tasks} class="tasks__row">
                <span class="tasks__task">
                  <strong>{task.name}</strong>
                  <span class="small quiet">{part_words(task.part)}</span>
                </span>
                <span class="tasks__number">
                  <span class="offscreen">Without the Skill</span>{reward_words(task.baseline_reward)}
                </span>
                <span class="tasks__number">
                  <span class="offscreen">With the Skill</span>{reward_words(task.candidate_reward)}
                </span>
                <span class="tasks__number">
                  <span class="offscreen">Change</span>{change_words(task)}
                </span>
              </li>
            </ol>
          </div>
        </Regent.Primitives.disclosure>

        <div id="showcase-skill-files">
          <Regent.Primitives.disclosure
            :for={{file, index} <- Enum.with_index(@showcase.skill.files, 2)}
            id={"showcase-skill-file-#{index}"}
            summary={"The Skill's file #{file.path}"}
            index={two_digits(index)}
            class="integrity-details"
          >
            <pre class="docs-code">{file.text}</pre>
          </Regent.Primitives.disclosure>
        </div>

        <Regent.Primitives.disclosure
          id="showcase-records"
          summary="Records and fingerprints"
          index={two_digits(length(@showcase.skill.files) + 2)}
          class="integrity-details"
        >
          <.definition_list>
            <:fact term="Comparison">{@showcase.comparison_id}</:fact>
            <:fact term="Compared on">{date(@showcase.created_at)}</:fact>
            <:fact term="Tasks">{@showcase.collection_id}</:fact>
            <:fact term="Fingerprint of the tasks"><.digest value={@showcase.fingerprint} /></:fact>
            <:fact term="Fingerprint of the Skill">
              <.digest value={@showcase.skill.digest} />
            </:fact>
          </.definition_list>
        </Regent.Primitives.disclosure>
      </section>

      <p class="small quiet section">
        <a href={~p"/results"}>Published Results</a> · <a href={~p"/start"}>Start</a>
      </p>
    </Layouts.page>
    """
  end

  attr :part, :map, required: true

  defp averages(assigns) do
    ~H"""
    <p :if={@part.graded > 0} class="assessment__means">
      {means(@part)} {extremes(@part)} {coverage(@part)}
    </p>
    """
  end

  attr :id, :string, required: true
  attr :groups, :map, required: true

  defp outcome_groups(assigns) do
    ~H"""
    <ul class="assessment__tasks">
      <li
        :for={outcome <- [:better, :worse, :same, :not_scored]}
        :if={outcome != :not_scored or @groups.not_scored != []}
        id={"#{@id}-#{outcome}"}
      >
        <strong>{group_words(outcome, length(@groups[outcome]))}</strong>
        <span :if={@groups[outcome] != []}>{Enum.map_join(@groups[outcome], ", ", &task_words/1)}</span>
      </li>
    </ul>
    """
  end

  attr :task, :map, required: true

  defp scores(assigns) do
    ~H"""
    <dl class="task-example__scores">
      <div>
        <dt>Without the Skill</dt>
        <dd>{reward_words(@task.baseline_reward)}</dd>
      </div>
      <div>
        <dt>With the Skill</dt>
        <dd>{reward_words(@task.candidate_reward)}</dd>
      </div>
      <div>
        <dt>Change</dt>
        <dd>{change_words(@task)}</dd>
      </div>
    </dl>
    """
  end

  # -- Words -------------------------------------------------------------------

  defp verdict_label(:improved), do: "Improved"
  defp verdict_label(:regressed), do: "Regressed"
  defp verdict_label(:mixed), do: "Mixed"
  defp verdict_label(:no_difference), do: "No difference"
  defp verdict_label(:inconclusive), do: "Not enough evidence"

  defp verdict_class(:inconclusive), do: "not_enough_evidence"
  defp verdict_class(verdict), do: Atom.to_string(verdict)

  defp reason(%{verdict: :improved} = part) do
    "On #{on(part)}, the agent did better with the Skill on #{tasks_words(part.wins)} and worse on none."
  end

  defp reason(%{verdict: :regressed} = part) do
    "On #{on(part)}, the agent did worse with the Skill on #{tasks_words(part.losses)} and better on none."
  end

  defp reason(%{verdict: :mixed} = part) do
    "On #{on(part)}, the agent did better with the Skill on #{tasks_words(part.wins)} and worse " <>
      "on #{tasks_words(part.losses)}, so the Skill helped on some and hurt on others."
  end

  defp reason(%{verdict: :no_difference} = part) do
    "On #{on(part)}, the agent did exactly as well with the Skill as without it."
  end

  defp reason(%{verdict: :inconclusive} = part),
    do: [too_few(part), unscored_sentence(part)] |> Enum.reject(&is_nil/1) |> Enum.join(" ")

  defp too_few(%{graded: graded}) do
    minimum = TddShowcase.verdict_minimum_pairs()

    if graded < minimum,
      do:
        "Too few held-out tasks have a score on both runs to decide: #{only(graded)}, and a " <>
          "decision needs at least #{minimum}."
  end

  defp only(0), do: "none do"
  defp only(1), do: "only 1 does"
  defp only(count), do: "only #{count} do"

  defp unscored_sentence(%{unresolved: 0}), do: nil

  defp unscored_sentence(%{unresolved: unresolved} = part) do
    "Of #{on(part)}, #{unresolved} #{has(unresolved)} no score from one of the runs, and a " <>
      "decision needs every one scored on both."
  end

  defp has(1), do: "has"
  defp has(_count), do: "have"

  defp on(%{tasks: [_task]}), do: "the one held-out task"
  defp on(part), do: "the #{length(part.tasks)} held-out tasks"

  defp other_tasks(1), do: "the other task"
  defp other_tasks(count), do: "the #{count} other tasks"

  defp means(part) do
    "On average #{ResultAssessment.reward(part.baseline_mean)} without the Skill, " <>
      "#{ResultAssessment.reward(part.candidate_mean)} with it " <>
      "(#{ResultAssessment.reward_change(part.baseline_mean, part.candidate_mean)})."
  end

  defp extremes(%{baseline_mean: +0.0, candidate_mean: +0.0}),
    do: "Neither run passed any of these tasks."

  defp extremes(%{baseline_mean: 1.0, candidate_mean: 1.0}),
    do: "Both runs passed every one of these tasks."

  defp extremes(_part), do: nil

  defp coverage(%{unresolved: 0}), do: nil

  defp coverage(%{graded: graded}),
    do: "These averages cover only the #{tasks_words(graded)} scored on both runs."

  defp task_words(%{unscored: []} = task), do: task.name

  defp task_words(task) do
    reasons =
      Enum.map_join(task.unscored, "; ", &"#{run_words(&1.run)}, #{ended_words(&1.ended)}")

    "#{task.name} (#{reasons})"
  end

  defp run_words(:baseline), do: "without the Skill"
  defp run_words(:candidate), do: "with the Skill"

  defp ended_words(:not_recorded), do: "the run stopped before this task"
  defp ended_words(:agent_timed_out), do: "the agent ran out of time"
  defp ended_words(:agent_failed), do: "the agent stopped with an error"
  defp ended_words(:outputs_rejected), do: "what the agent left could not be kept for checking"
  defp ended_words(:verifier_timed_out), do: "the checker ran out of time"
  defp ended_words(:no_verdict), do: "the checker gave no verdict"

  defp group_words(:better, count), do: "Better on #{tasks_words(count)}#{colon(count)}"
  defp group_words(:worse, count), do: "Worse on #{tasks_words(count)}#{colon(count)}"
  defp group_words(:same, count), do: "No change on #{tasks_words(count)}#{colon(count)}"

  defp group_words(:not_scored, count),
    do: "Missing a score from one run on #{tasks_words(count)}:"

  defp tasks_words(0), do: "no tasks"
  defp tasks_words(1), do: "1 task"
  defp tasks_words(count), do: "#{count} tasks"

  defp colon(0), do: "."
  defp colon(_count), do: ":"

  defp outcome_label(:better), do: "Better with the Skill"
  defp outcome_label(:worse), do: "Worse with the Skill"
  defp outcome_label(:same), do: "No change"
  defp outcome_label(:not_scored), do: "Not scored on both runs"

  defp kind_words("positive"), do: "Positive case"
  defp kind_words("boundary"), do: "Boundary case"
  defp kind_words("counterexample"), do: "Counterexample"

  defp part_words(:held_out), do: "Held out"
  defp part_words(:study), do: "Seen by the improving agent"

  defp reward_words(nil), do: "Not scored"
  defp reward_words(reward), do: ResultAssessment.reward(reward)

  defp change_words(%{baseline_reward: baseline, candidate_reward: candidate})
       when is_nil(baseline) or is_nil(candidate),
       do: "None"

  defp change_words(task),
    do: ResultAssessment.reward_change(task.baseline_reward, task.candidate_reward)

  defp model_words(%{provider: provider, model_id: model_id, reasoning: nil}),
    do: "#{model_id} from #{Providers.name!(provider)}"

  defp model_words(%{provider: provider, model_id: model_id, reasoning: reasoning}),
    do: "#{model_id} from #{Providers.name!(provider)}, with #{reasoning} reasoning"

  defp time_limit_words(tasks) do
    case tasks |> Enum.map(& &1.time_limit) |> Enum.uniq() do
      [limit] -> "Time: #{limit} for each try."
      _limits -> "Time: each task's own limit, shown with the task."
    end
  end

  defp limits_words(%{cpus: cpus, memory_mb: memory_mb}),
    do: "#{cpus_words(cpus)}, #{memory_words(memory_mb)} of memory"

  defp cpus_words(1), do: "1 processor core"
  defp cpus_words(cpus), do: "#{cpus} processor cores"

  defp memory_words(memory_mb) when rem(memory_mb, 1024) == 0, do: "#{div(memory_mb, 1024)} GB"
  defp memory_words(memory_mb), do: "#{memory_mb} MB"

  defp not_established_words(:served_model),
    do:
      "Which model the provider actually served. Only the provider's own report, passed on " <>
        "by Hermes, says which model answered."

  defp not_established_words(:agent_unmodified),
    do: "That the Hermes agent program was unmodified. Its version is only what it reports."

  defp not_established_words(:sampling),
    do:
      "How the model chose its answers. Those settings cannot be changed, so every try used " <>
        "the provider's defaults."

  defp two_digits(index), do: index |> Integer.to_string() |> String.pad_leading(2, "0")

  defp usage_words(%{api_calls: calls, total_tokens: tokens}),
    do:
      "#{count_words(calls, "model call", "model calls")}, #{count_words(tokens, "token", "tokens")}"

  defp count_words(nil, _one, many), do: "#{many} not reported"
  defp count_words(1, one, _many), do: "1 #{one}"
  defp count_words(count, _one, many), do: "#{TechtreeWeb.CampaignFacts.count(count)} #{many}"

  defp date(at), do: Calendar.strftime(at, "%-d %B %Y")
end
