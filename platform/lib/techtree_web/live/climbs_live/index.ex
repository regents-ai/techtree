defmodule TechtreeWeb.ClimbsLive.Index do
  @moduledoc """
  The Climbs this release offers, with enough of each to choose between them.

  No ranking, no scores, no counts of who has entered. A Climb is described by
  what it measures, what it holds fixed, what it does with your work, and what
  a result from it may be called.
  """

  use TechtreeWeb, :live_view

  alias Techtree.Catalog.Query
  alias TechtreeWeb.ClimbCopy

  @impl true
  def mount(_params, _session, socket) do
    {:ok,
     socket
     |> assign(page_title: "Climbs")
     |> assign(cards: Enum.map(Query.list_climbs(), &card/1))}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page wide>
      <h1>Climbs</h1>
      <p class="lede">
        Each Climb is one question, asked the same way every time it is run.
      </p>

      <p :if={@cards == []} class="section">
        No Climbs are published on this site at the moment. The command-line tool
        ships with the Climbs it can run, so this page being empty does not stop a
        trial on your own machine.
      </p>

      <div :if={@cards != []} class="entries">
        <article :for={card <- @cards} class="entry">
          <div class="entry__head">
            <h2 class="entry__title">
              <a href={~p"/climbs/#{slug(card.climb)}"}>{card.climb.title}</a>
            </h2>
            <.status_badge status={card.climb.status} />
          </div>

          <p :if={card.copy} class="plain quiet">{card.copy.subtitle}</p>

          <p>{card.climb.summary}</p>

          <.definition_list>
            <:fact term="The question">{purpose_words(fact(card.climb, "purpose"))}</:fact>
            <:fact :if={card.copy} term="The trial">{card.copy.campaign_title}</:fact>
            <:fact term="What may differ">
              {mutation_words(get_in(card.climb.projection, ["mutation_contract", "kind"]))}
            </:fact>
            <:fact term="Tasks">{fact(card.climb, "task_count")}</:fact>
            <:fact :if={card.copy} term="Task family">{card.copy.task_family}</:fact>
            <:fact term="The agent under test">
              {fact(card.climb, "subject_harness")} {fact(card.climb, "subject_harness_version")}
            </:fact>
            <:fact term="On your machine">
              Docker, macOS or Linux, and your own model provider key.
            </:fact>
            <:fact term="What a result may be called">
              {proof_grade_words(fact(card.climb, "proof_grade"))}
            </:fact>
            <:fact
              :for={{term, sentence} <- data_policy_lines(fact(card.climb, "data_policy"))}
              term={term}
            >
              {sentence}
            </:fact>
            <:fact term="Reference">
              <span class="digest">{card.climb.reference}</span>
            </:fact>
          </.definition_list>
        </article>
      </div>
    </Layouts.page>
    """
  end

  defp card(climb), do: %{climb: climb, copy: ClimbCopy.for_reference(climb.reference)}

  defp fact(climb, key), do: Map.get(climb.projection, key)

  defp slug(climb), do: fact(climb, "slug")
end
