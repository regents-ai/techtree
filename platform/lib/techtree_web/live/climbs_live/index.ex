defmodule TechtreeWeb.ClimbsLive.Index do
  @moduledoc """
  The Climbs this release offers, with enough of each to choose between them.

  No ranking, no scores, no counts of who has entered. A Climb is described by
  what it measures, what it holds fixed, what it does with your work, and what
  a result from it may be called.
  """

  use TechtreeWeb, :live_view

  alias Techtree.Catalog.Query

  @impl true
  def mount(_params, _session, socket) do
    {:ok,
     socket
     |> assign(page_title: "Climbs")
     |> assign(climbs: Query.list_climbs())}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page wide>
      <h1>Climbs</h1>
      <p class="lede">
        Each Climb is one question, asked the same way every time it is run.
      </p>

      <p :if={@climbs == []} class="section">
        No Climbs are published on this site at the moment. The command-line tool
        ships with the Climbs it can run, so this page being empty does not stop a
        trial on your own machine.
      </p>

      <div :if={@climbs != []} class="entries">
        <article :for={climb <- @climbs} class="entry">
          <div class="entry__head">
            <h2 class="entry__title">
              <a href={~p"/climbs/#{slug(climb)}"}>{climb.title}</a>
            </h2>
            <.status_badge status={climb.status} />
          </div>

          <p>{climb.summary}</p>

          <.definition_list>
            <:fact term="The question">{purpose_words(fact(climb, "purpose"))}</:fact>
            <:fact term="What may differ">
              {mutation_words(get_in(climb.projection, ["mutation_contract", "kind"]))}
            </:fact>
            <:fact term="Tasks">
              {fact(climb, "task_count")} tasks from {fact(climb, "taskset_id")}
            </:fact>
            <:fact term="The agent under test">
              {fact(climb, "subject_harness")} {fact(climb, "subject_harness_version")}
            </:fact>
            <:fact term="On your machine">
              Docker, macOS or Linux, and your own model provider key.
            </:fact>
            <:fact term="What a result may be called">
              {proof_grade_words(fact(climb, "proof_grade"))}
            </:fact>
            <:fact
              :for={{term, sentence} <- data_policy_lines(fact(climb, "data_policy"))}
              term={term}
            >
              {sentence}
            </:fact>
            <:fact term="Reference">
              <span class="digest">{climb.reference}</span>
            </:fact>
          </.definition_list>
        </article>
      </div>
    </Layouts.page>
    """
  end

  defp fact(climb, key), do: Map.get(climb.projection, key)

  defp slug(climb), do: fact(climb, "slug")
end
