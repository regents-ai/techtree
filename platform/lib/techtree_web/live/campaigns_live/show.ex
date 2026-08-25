defmodule TechtreeWeb.CampaignsLive.Show do
  @moduledoc """
  One campaign's fixed coordinates and the real artifacts behind its graph.
  """

  use TechtreeWeb, :live_view

  alias Techtree.Catalog.Query
  alias TechtreeWeb.ClimbCopy
  alias TechtreeWeb.EvidenceComponents
  alias TechtreeWeb.EvidenceGraph

  @impl true
  def mount(%{"slug" => slug}, _session, socket) do
    case Query.get_climb_by_slug(slug) do
      {:ok, climb} ->
        copy = ClimbCopy.for_reference(climb.reference)

        {:ok,
         assign(socket,
           page_title: (copy && copy.campaign_title) || climb.title,
           climb: climb,
           copy: copy,
           graph: EvidenceGraph.from_climb(climb)
         )}

      {:error, _error} ->
        raise TechtreeWeb.NotFoundError, "no campaign is published under that name"
    end
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page wide>
      <p class="back-link"><a href={~p"/campaigns"}>← All campaigns</a></p>
      <header class="page-heading page-heading--split">
        <div>
          <p class="eyebrow">Campaign · {@climb.status}</p>
          <h1>{(@copy && @copy.campaign_title) || @climb.title}</h1>
          <p class="lede">{@climb.summary}</p>
        </div>
        <p class="digest">{@climb.projection["campaign_spec_digest"]}</p>
      </header>

      <EvidenceComponents.graph id="campaign-evidence-graph" nodes={@graph} />

      <div class="campaign-detail">
        <section>
          <p class="eyebrow">Held fixed</p>
          <h2>Comparison coordinates</h2>
          <.definition_list>
            <:fact term="Tasks">{@climb.projection["task_count"]}</:fact>
            <:fact term="Harness">
              {@climb.projection["subject_harness"]}
              {@climb.projection["subject_harness_version"]}
            </:fact>
            <:fact term="Model">{model_coordinate(@climb.projection["subject_model"])}</:fact>
            <:fact term="Runtime">{runtime(@climb.projection["subject_runtime"])}</:fact>
            <:fact term="Scoring">
              {@climb.projection["scoring"]["primary_reward"]}, {@climb.projection["scoring"][
                "aggregation"
              ]}
            </:fact>
            <:fact term="Budget">{budget(@climb.projection["budget"])}</:fact>
          </.definition_list>
        </section>

        <section>
          <p class="eyebrow">Declared change</p>
          <h2>One Skill</h2>
          <p>{mutation_words(@climb.projection["mutation_contract"]["kind"])}</p>
          <p>
            The candidate Skill digest is recorded when a participant prepares the run.
            Until then, the public campaign declares the slot without pretending a
            candidate exists.
          </p>
        </section>
      </div>

      <section class="artifact-strip" aria-labelledby="artifact-title">
        <div>
          <p class="eyebrow">Source objects</p>
          <h2 id="artifact-title">Every claim has an address.</h2>
        </div>
        <a href={object_url(@climb.projection["campaign_spec_digest"])}>CampaignSpec</a>
        <a href={object_url(@climb.projection["validation_receipt_digest"])}>
          Task validation
        </a>
        <a href={object_url(@climb.projection["data_policy_digest"])}>Data policy</a>
      </section>
    </Layouts.page>
    """
  end

  defp model_coordinate(model) when is_map(model) do
    [model["provider"], model["model_id"], model["revision"]]
    |> Enum.reject(&(&1 in [nil, ""]))
    |> Enum.join(" · ")
  end

  defp model_coordinate(_model), do: "Not published"

  defp runtime(runtime) when is_map(runtime) do
    "#{runtime["type"]} · #{runtime["cpu"]} CPU · #{runtime["memory_gb"]} GB · " <>
      "#{runtime["network_policy"]} network"
  end

  defp runtime(_runtime), do: "Not published"

  defp budget(%{
         "maximum_model_calls" => calls,
         "maximum_input_tokens" => input_tokens,
         "maximum_output_tokens" => output_tokens
       }),
       do:
         "#{calls} model calls · #{input_tokens} input tokens · " <>
           "#{output_tokens} output tokens maximum"

  defp budget(_budget), do: "Not published"

  defp object_url(digest), do: "/api/v1/objects/" <> digest
end
