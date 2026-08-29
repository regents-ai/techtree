defmodule TechtreeWeb.ClimbsLive.Show do
  @moduledoc """
  The concise contract and setup instruction for one published Climb.
  """

  use TechtreeWeb, :live_view

  alias Techtree.Catalog.Query
  alias TechtreeWeb.ClimbCopy

  @instruction "Set up Techtree and run the Hello World Climb."

  @impl true
  def mount(%{"slug" => slug}, _session, socket) do
    case Query.get_climb_by_slug(slug) do
      {:ok, climb} ->
        {:ok,
         assign(socket,
           page_title: climb.title,
           climb: climb,
           copy: ClimbCopy.for_reference(climb.reference),
           instruction: @instruction
         )}

      {:error, _error} ->
        raise TechtreeWeb.NotFoundError, "no Climb is published under that name"
    end
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page>
      <article class="climb-contract">
        <header>
          <p class="eyebrow">Climb</p>
          <h1>{@climb.title}</h1>
          <p :if={@copy} class="lede">{@copy.scope}</p>
        </header>

        <dl class="climb-contract__facts">
          <div>
            <dt>Question</dt>
            <dd>{purpose_words(@climb.projection["purpose"])}</dd>
          </div>
          <div>
            <dt>Changed</dt>
            <dd>{mutation_words(get_in(@climb.projection, ["mutation_contract", "kind"]))}</dd>
          </div>
          <div>
            <dt>Tasks</dt>
            <dd>{@climb.projection["task_count"]}</dd>
          </div>
          <div>
            <dt>Held fixed</dt>
            <dd>
              {@climb.projection["subject_harness"]} {@climb.projection["subject_harness_version"]}, {@climb.projection[
                "subject_model"
              ]["provider"]} {@climb.projection["subject_model"]["model_id"]}
            </dd>
          </div>
        </dl>

        <section class="climb-contract__start" aria-labelledby="climb-setup-instruction">
          <h2 id="climb-setup-instruction">{@instruction}</h2>
          <button
            id="copy-climb-setup-instruction"
            class="setup-page__copy"
            type="button"
            phx-hook="CopyCommand"
            phx-update="ignore"
            data-copy-value={@instruction}
          >
            <span data-copy-label>Copy</span>
          </button>
        </section>
      </article>
    </Layouts.page>
    """
  end
end
