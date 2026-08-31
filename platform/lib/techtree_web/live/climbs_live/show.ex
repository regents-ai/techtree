defmodule TechtreeWeb.ClimbsLive.Show do
  @moduledoc """
  The concise contract and setup instruction for one published Climb.
  """

  use TechtreeWeb, :live_view

  alias Techtree.Catalog.Query
  alias TechtreeWeb.ClimbCopy

  @impl true
  def mount(%{"slug" => slug}, _session, socket) do
    case Query.get_climb_by_slug(slug) do
      {:ok, climb} ->
        {:ok,
         assign(socket,
           page_title: climb.title,
           climb: climb,
           copy: ClimbCopy.for_reference(climb.reference)
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
            <dd>{(@copy && @copy.question) || purpose_words(@climb.projection["purpose"])}</dd>
          </div>
          <div>
            <dt>Changed</dt>
            <dd>{mutation_words(get_in(@climb.projection, ["mutation_contract", "kind"]))}</dd>
          </div>
          <div>
            <dt>Tasks</dt>
            <dd>{@climb.projection["task_count"]}, fixed before either Run</dd>
          </div>
          <div>
            <dt>Input</dt>
            <dd>{(@copy && @copy.input) || "Defined by the published task set."}</dd>
          </div>
          <div>
            <dt>Expected output</dt>
            <dd>{(@copy && @copy.output) || "Defined by the published scorer."}</dd>
          </div>
          <div>
            <dt>Scoring</dt>
            <dd>{(@copy && @copy.scoring) || "Defined by the published Climb."}</dd>
          </div>
          <div>
            <dt>Held fixed</dt>
            <dd>{(@copy && @copy.held_fixed) || held_fixed_words(@climb)}</dd>
          </div>
        </dl>

        <p class="small quiet section">
          <a href={~p"/results"}>Browse Results from published Climbs</a>
        </p>
      </article>
    </Layouts.page>
    """
  end

  defp held_fixed_words(climb) do
    "#{climb.projection["subject_harness"]} #{climb.projection["subject_harness_version"]}, " <>
      "#{climb.projection["subject_model"]["provider"]} " <>
      climb.projection["subject_model"]["model_id"]
  end
end
