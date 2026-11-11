defmodule TechtreeWeb.TrainLive.Index do
  @moduledoc """
  The Train page: NVIDIA Nemotron models measured before and after one change,
  on the same held-out tasks with the same settings. The newest comparison
  leads with its figures and its strip of task results; every comparison is
  listed under it, each opening its own page (`TechtreeWeb.TrainLive.Show`);
  and Private offers bespoke RL training on a customer's own tasks, by email.

  The comparisons are the committed reports (`Techtree.Train.Comparisons`),
  read as the page opens. Until there is one, the page says so.
  """

  use TechtreeWeb, :live_view

  alias Techtree.Train.Comparisons
  alias TechtreeWeb.TrainCopy, as: Copy

  import TechtreeWeb.TrainLive.Parts

  @impl true
  def mount(_params, _session, socket) do
    {:ok,
     assign(socket,
       page_title: "Train",
       comparisons: Comparisons.list(),
       mailto: Copy.private_mailto()
     )}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page wide>
      <div class="train">
        <header class="page-heading">
          <p class="eyebrow">NVIDIA Nemotron · Prime Intellect</p>
          <h1>Train</h1>
          <p class="lede">
            NVIDIA Nemotron models before and after one change, on the same held-out tasks with the same settings.
          </p>
        </header>

        <p :if={@comparisons == []} id="train-empty" class="empty-state" role="status">
          No comparisons yet. Each one will show a Nemotron model's score before and after its change, task by task.
        </p>

        <.lead :if={@comparisons != []} comparison={hd(@comparisons)} />

        <section
          :if={length(@comparisons) > 1}
          id="train-comparisons"
          class="section"
          aria-labelledby="train-comparisons-title"
        >
          <h2 id="train-comparisons-title">Comparisons</h2>
          <ol
            id="train-list"
            class="train-list"
            phx-hook="MotionCascade"
            data-variant={TechtreeWeb.Motion.standard("grid")}
          >
            <li
              :for={comparison <- @comparisons}
              id={"comparison-#{comparison.slug}"}
              class="train-list__item"
            >
              <div class="train-list__name">
                <.link navigate={~p"/train/#{comparison.slug}"}>{comparison.title}</.link>
                <span class="small quiet">
                  {comparison.model.family} · {Copy.date(comparison.operational.finished_at)}
                </span>
              </div>
              <p class="train-list__figures">
                <span :for={arm <- comparison.arms}>
                  <span class="quiet">{Copy.arm_label(comparison, arm)}</span>
                  {Copy.percent(arm.mean_reward)}
                </span>
              </p>
              <.outcome outcome={comparison.outcome} />
            </li>
          </ol>
        </section>

        <section id="private" class="section" aria-labelledby="private-title">
          <Regent.Structure.panel class="train-private rg-panel__body rg-support-panel">
            <h2 id="private-title">Private</h2>
            <p>
              Bespoke RL training on your own tasks: an NVIDIA Nemotron model trained on Prime Intellect and measured the same way, before and after. Results stay private to your team.
            </p>
            <a class="rg-button rg-button--primary" href={@mailto}>Email build@regents.sh</a>
          </Regent.Structure.panel>
        </section>
      </div>
    </Layouts.page>
    """
  end

  attr :comparison, :map, required: true

  defp lead(assigns) do
    ~H"""
    <section id="train-lead" class="train-lead" aria-labelledby="train-lead-title">
      <div class="train-lead__head">
        <p class="eyebrow">Latest · {Copy.date(@comparison.operational.finished_at)}</p>
        <h2 id="train-lead-title">
          <.link navigate={~p"/train/#{@comparison.slug}"}>{@comparison.title}</.link>
        </h2>
        <.outcome outcome={@comparison.outcome} />
      </div>
      <.figures comparison={@comparison} />
      <.strip comparison={@comparison} />
      <p class="train-lead__line">
        {Copy.paired(@comparison.paired)} · 95% interval {Copy.interval(@comparison.paired.ci95)} points · {@comparison.environment.task_count} held-out tasks
      </p>
      <div class="train-lead__actions">
        <.link navigate={~p"/train/#{@comparison.slug}"} class="rg-button rg-button--primary">
          Details
        </.link>
        <.link navigate={~p"/train/#{@comparison.slug}" <> "#settings"} class="text-link">
          Settings <span aria-hidden="true">→</span>
        </.link>
      </div>
    </section>
    """
  end
end
