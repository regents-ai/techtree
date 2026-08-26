defmodule TechtreeWeb.CampaignsLive.Index do
  @moduledoc """
  The campaigns this release publishes, in the order the catalog ships them.

  There is no ranking here and no result: a campaign is a comparison that has
  been fixed in advance, and this page says what was fixed. Anything that would
  need a run to be true is somewhere else, or nowhere.
  """

  use TechtreeWeb, :live_view

  alias Techtree.Catalog.Query
  alias TechtreeWeb.CampaignFacts
  alias TechtreeWeb.ClimbCopy

  @impl true
  def mount(_params, _session, socket) do
    campaigns = Enum.map(Query.list_climbs(), &card/1)
    {:ok, assign(socket, page_title: "Campaigns", campaigns: campaigns)}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page wide>
      <header class="page-heading">
        <p class="eyebrow">Published by this release</p>
        <h1>Campaigns</h1>
        <p class="lede">
          Each campaign fixes the comparison — tasks, model, harness, runtime, scoring
          and ceiling — before either branch runs.
        </p>
      </header>

      <p :if={@campaigns == []} class="empty-state">
        No campaign is published on this channel.
      </p>

      <div :if={@campaigns != []} class="campaign-list">
        <article :for={card <- @campaigns} class="campaign-card">
          <div class="campaign-card__header">
            <div>
              <p class="eyebrow">Campaign</p>
              <h2>{card.title}</h2>
            </div>
            <.status_badge status={card.climb.status} />
          </div>
          <p>{card.climb.summary}</p>
          <dl class="campaign-card__facts">
            <div>
              <dt>Tasks</dt>
              <dd>{CampaignFacts.membership_words(card.facts.membership) || "Not published"}</dd>
            </div>
            <div>
              <dt>Harness</dt>
              <dd>
                {card.climb.projection["subject_harness"]}
                {card.climb.projection["subject_harness_version"]}
              </dd>
            </div>
            <div>
              <dt>Model</dt>
              <dd>{model_coordinate(card.climb.projection["subject_model"])}</dd>
            </div>
          </dl>
          <a class="text-link" href={~p"/campaigns/#{card.climb.projection["slug"]}"}>
            Inspect campaign <span aria-hidden="true">→</span>
          </a>
        </article>
      </div>
    </Layouts.page>
    """
  end

  defp card(climb) do
    copy = ClimbCopy.for_reference(climb.reference)

    %{
      climb: climb,
      facts: CampaignFacts.for_climb(climb),
      title: (copy && copy.campaign_title) || climb.title
    }
  end

  defp model_coordinate(model) when is_map(model) do
    [model["provider"], model["model_id"], model["revision"]]
    |> Enum.reject(&(&1 in [nil, ""]))
    |> Enum.join(" · ")
  end

  defp model_coordinate(_model), do: "Not published"
end
