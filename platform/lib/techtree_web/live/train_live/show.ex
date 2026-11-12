defmodule TechtreeWeb.TrainLive.Show do
  @moduledoc """
  One Train comparison: the two arms' mean rewards and their difference, the
  outcome with the paired wins, ties and losses and the 95% interval, each
  arm side by side, every task's result, the exact settings, environment and
  model, and the digests with the report and its traces to download.

  The comparison is one committed report (`Techtree.Train.Comparisons`); a
  slug the folder has no report for, or one that was refused, is a 404.
  """

  use TechtreeWeb, :live_view

  alias Techtree.Train.Comparisons
  alias TechtreeWeb.TrainCopy, as: Copy

  import TechtreeWeb.TrainLive.Parts

  @impl true
  def mount(%{"slug" => slug}, _session, socket) do
    case Comparisons.fetch(slug) do
      {:ok, comparison} ->
        {:ok, assign(socket, page_title: comparison.title, comparison: comparison)}

      :error ->
        raise TechtreeWeb.NotFoundError, "no Train comparison has that name"
    end
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page wide>
      <div class="train">
        <p class="back-link"><.link navigate={~p"/train"}>← Train</.link></p>

        <header class="page-heading">
          <p class="eyebrow">
            {Copy.change(@comparison.change)} · {Copy.date(@comparison.operational.finished_at)}
          </p>
          <h1>{@comparison.title}</h1>
          <p class="lede">
            {@comparison.model.family} on {@comparison.environment.task_count} held-out tasks of {@comparison.environment.id}, with the same settings on both sides.
          </p>
        </header>

        <section id="result" class="train-lead" aria-labelledby="result-title">
          <div class="train-lead__head">
            <h2 id="result-title">Result</h2>
            <.outcome outcome={@comparison.outcome} />
          </div>
          <.figures comparison={@comparison} />
          <dl class="train-paired">
            <div>
              <dt>Wins</dt>
              <dd>{@comparison.paired.wins}</dd>
            </div>
            <div>
              <dt>Ties</dt>
              <dd>{@comparison.paired.ties}</dd>
            </div>
            <div>
              <dt>Losses</dt>
              <dd>{@comparison.paired.losses}</dd>
            </div>
            <div>
              <dt>Interval</dt>
              <dd>{Copy.interval(@comparison.paired.ci95)}</dd>
            </div>
          </dl>
          <p class="small quiet">
            Mean reward per arm. The interval is the 95% range of the difference in points, by {@comparison.paired.method}.
          </p>
        </section>

        <section id="arms" class="section" aria-labelledby="arms-title">
          <h2 id="arms-title">Arms</h2>
          <div class="train-arms">
            <Regent.Structure.panel
              :for={arm <- @comparison.arms}
              id={"arm-#{arm.name}"}
              class="train-arm rg-panel__body"
            >
              <h3>{Copy.arm_label(@comparison, arm)}</h3>
              <.definition_list>
                <:fact term="Arm"><code>{arm.name}</code></:fact>
                <:fact term="Mean reward">{Copy.percent(arm.mean_reward)}</:fact>
                <:fact term="Solved">{Copy.solved(arm, @comparison.environment.task_count)}</:fact>
                <:fact term="Completion tokens">{Copy.number(arm.completion_tokens)}</:fact>
                <:fact :if={arm.skill_digest} term="Skill">
                  <.copyable
                    id={"arm-#{arm.name}-skill"}
                    value={arm.skill_digest}
                    label="Copy Skill digest"
                  />
                </:fact>
                <:fact :if={arm.adapter} term="Adapter">
                  <.copyable
                    id={"arm-#{arm.name}-adapter"}
                    value={arm.adapter}
                    label="Copy adapter name"
                  />
                </:fact>
              </.definition_list>
            </Regent.Structure.panel>
          </div>
        </section>

        <section id="tasks" class="section" aria-labelledby="tasks-title">
          <h2 id="tasks-title">Tasks</h2>
          <.strip comparison={@comparison} />
          <p class="train-legend small">
            <span class="train-legend__item train-legend__item--win">
              {@comparison.paired.wins} {plural(@comparison.paired.wins, "win", "wins")}
            </span>
            <span class="train-legend__item train-legend__item--tie">
              {@comparison.paired.ties} {plural(@comparison.paired.ties, "tie", "ties")}
            </span>
            <span class="train-legend__item train-legend__item--loss">
              {@comparison.paired.losses} {plural(@comparison.paired.losses, "loss", "losses")}
            </span>
          </p>
          <details id="every-task" class="train-tasks">
            <summary>Every task</summary>
            <div class="train-tasks__frame" role="region" aria-label="Every task" tabindex="0">
              <table class="train-tasks__table">
                <thead>
                  <tr>
                    <th scope="col">Task</th>
                    <th :for={arm <- @comparison.arms} scope="col">
                      {Copy.arm_label(@comparison, arm)}
                    </th>
                    <th scope="col">Result</th>
                  </tr>
                </thead>
                <tbody>
                  <tr :for={task <- @comparison.tasks} id={"task-#{task.id}"}>
                    <th scope="row"><code>{task.id}</code></th>
                    <td :for={{reward, solved} <- arm_scores(task)}>
                      {Copy.reward(reward)}<span :if={solved} class="quiet"> · solved</span>
                    </td>
                    <td class={"train-tasks__result train-tasks__result--#{task.result}"}>
                      {Copy.result(task.result)}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </details>
        </section>

        <section id="settings" class="section" aria-labelledby="settings-title">
          <h2 id="settings-title">Settings</h2>
          <div class="train-settings">
            <div>
              <h3>Sampling</h3>
              <.definition_list>
                <:fact term="Temperature">{@comparison.sampling.temperature}</:fact>
                <:fact term="Max tokens">{Copy.number(@comparison.sampling.max_tokens)}</:fact>
                <:fact term="Thinking">
                  {if @comparison.sampling.thinking, do: "On", else: "Off"}
                </:fact>
              </.definition_list>
            </div>
            <div>
              <h3>Environment</h3>
              <.definition_list>
                <:fact term="Name"><code>{@comparison.environment.id}</code></:fact>
                <:fact term="Version">{@comparison.environment.version}</:fact>
                <:fact term="Split">{Copy.split(@comparison.environment.split)}</:fact>
                <:fact term="Seed">{@comparison.environment.seed}</:fact>
                <:fact term="Tasks">{@comparison.environment.task_count}</:fact>
              </.definition_list>
            </div>
            <div>
              <h3>Model</h3>
              <.definition_list>
                <:fact term="Family">NVIDIA {@comparison.model.family}</:fact>
                <:fact term="Name"><code>{@comparison.model.name}</code></:fact>
                <:fact term="Provider">{@comparison.model.provider}</:fact>
              </.definition_list>
            </div>
            <div>
              <h3>Run</h3>
              <.definition_list>
                <:fact term="Host">{@comparison.operational.host}</:fact>
                <:fact term="Started">{Copy.time(@comparison.operational.started_at)}</:fact>
                <:fact term="Length">{Copy.duration(@comparison.operational.duration_seconds)}</:fact>
                <:fact term="Run cost">${@comparison.operational.cost_usd}</:fact>
                <:fact term="Verifiers">{@comparison.software.verifiers}</:fact>
                <:fact term="techtree-lab">{@comparison.software.techtree_lab}</:fact>
              </.definition_list>
            </div>
          </div>
        </section>

        <section id="evidence" class="section" aria-labelledby="evidence-title">
          <h2 id="evidence-title">Evidence</h2>
          <.definition_list>
            <:fact term="Report">
              <.copyable id="digest-report" value={@comparison.digest} label="Copy report digest" />
            </:fact>
            <:fact term="Traces">
              <.copyable
                id="digest-traces"
                value={@comparison.traces_digest}
                label="Copy traces digest"
              />
            </:fact>
            <:fact term="Tasks">
              <.copyable
                id="digest-tasks"
                value={@comparison.environment.taskset_digest}
                label="Copy tasks digest"
              />
            </:fact>
            <:fact term="Weights">
              <.copyable
                id="digest-weights"
                value={@comparison.model.weights_digest}
                label="Copy weights digest"
              />
            </:fact>
          </.definition_list>
          <div class="train-downloads">
            <a
              class="rg-button rg-button--primary rg-button--no-arrow"
              href={~p"/train/#{@comparison.slug}/report.json"}
              download={"#{@comparison.slug}.json"}
            >
              <Regent.Icons.icon name="download" /> Report
            </a>
            <a
              class="rg-button rg-button--no-arrow"
              href={~p"/train/#{@comparison.slug}/traces.jsonl"}
              download={"#{@comparison.slug}.traces.jsonl"}
            >
              <Regent.Icons.icon name="download" /> Traces
            </a>
          </div>
        </section>
      </div>
    </Layouts.page>
    """
  end

  attr :id, :string, required: true
  attr :value, :string, required: true
  attr :label, :string, required: true

  defp copyable(assigns) do
    ~H"""
    <span class="train-copyable">
      <.digest value={@value} />
      <Regent.Primitives.copy_icon id={@id} text={@value} label={@label} />
    </span>
    """
  end

  defp arm_scores(%{rewards: {before, changed}, solved: {before_solved, changed_solved}}),
    do: [{before, before_solved}, {changed, changed_solved}]

  defp plural(1, one, _many), do: one
  defp plural(_count, _one, many), do: many
end
