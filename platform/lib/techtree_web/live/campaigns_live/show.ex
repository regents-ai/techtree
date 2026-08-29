defmodule TechtreeWeb.CampaignsLive.Show do
  @moduledoc """
  One campaign's fixed coordinates, and the documents every one of them is
  read from.

  Everything on this page has an address. The fingerprints are not decoration:
  they are how a reader checks that the campaign described here is the campaign
  their machine will resolve, and every one of them links to the exact bytes.
  """

  use TechtreeWeb, :live_view

  alias Techtree.Catalog.Query
  alias Techtree.Network.Query, as: NetworkQuery
  alias Techtree.Release.StarterSkill
  alias TechtreeWeb.CampaignFacts
  alias TechtreeWeb.ClimbCopy
  alias TechtreeWeb.EvidenceComponents
  alias TechtreeWeb.EvidenceGraph
  alias TechtreeWeb.ReleaseInfo

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
           facts: climb.projection,
           published: CampaignFacts.for_climb(climb),
           graph:
             EvidenceGraph.from_climb(
               climb,
               ReleaseInfo.current(),
               NetworkQuery.for_campaign(climb.projection["campaign_spec_digest"])
             )
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
          <p class="eyebrow">Campaign</p>
          <h1>{(@copy && @copy.campaign_title) || @climb.title}</h1>
          <p class="lede">{@climb.summary}</p>
          <.status_badge status={@climb.status} />
        </div>
        <.digest
          value={@facts["campaign_spec_digest"]}
          href={object_url(@facts["campaign_spec_digest"])}
        />
      </header>

      <EvidenceComponents.graph id="campaign-evidence-graph" nodes={@graph} />

      <div class="campaign-detail">
        <section>
          <p class="eyebrow">Held fixed</p>
          <h2>Comparison coordinates</h2>
          <.definition_list>
            <:fact term="Tasks">
              {CampaignFacts.membership_words(@published.membership) || "Not published"}
            </:fact>
            <:fact term="Task list">
              <.digest value={@published.membership["membership_digest"] || "Not published"} />
            </:fact>
            <:fact term="Harness">
              {@facts["subject_harness"]} {@facts["subject_harness_version"]}
            </:fact>
            <:fact term="Model">{model_coordinate(@facts["subject_model"])}</:fact>
            <:fact term="Where it runs">{runtime_words(@facts["subject_runtime"])}</:fact>
            <:fact term="Scoring">{scoring_words(@facts["scoring"])}</:fact>
            <:fact term="Ceiling">
              {CampaignFacts.budget_words(@published.budget) || "Not published"}
            </:fact>
          </.definition_list>
          <p class="small quiet">
            A run may not exceed the ceiling. What the calls themselves cost is set by
            your model provider, and this site cannot say what that will be.
          </p>
        </section>

        <section>
          <p class="eyebrow">Declared change</p>
          <h2>One Skill</h2>
          <p :if={@copy} class="campaign-skill">
            Starter Skill:
            <a id="campaign-starter-skill" href={starter_skill_url()}>{@copy.starter_skill}</a>
          </p>
          <p>{mutation_words(get_in(@facts, ["mutation_contract", "kind"]))}</p>
          <p>
            The candidate Skill is recorded when a participant prepares the run. Until
            then this page declares the slot rather than pretending a candidate exists.
          </p>
          <p :if={@copy} class="small quiet">{@copy.starter_note}</p>
        </section>
      </div>

      <section class="doc-section">
        <p class="eyebrow">What this asks of you</p>
        <h2>The terms attached to a result</h2>
        <.definition_list>
          <:fact :for={{term, sentence} <- data_policy_lines(@facts["data_policy"])} term={term}>
            {sentence}
          </:fact>
        </.definition_list>
      </section>

      <section class="artifact-strip" aria-labelledby="artifact-title">
        <div>
          <p class="eyebrow">Source documents</p>
          <h2 id="artifact-title">Every claim has an address.</h2>
        </div>
        <a href={object_url(@facts["campaign_spec_digest"])}>Campaign definition</a>
        <a href={object_url(@facts["validation_receipt_digest"])}>Task validation</a>
        <a href={object_url(@facts["data_policy_digest"])}>Data policy</a>
      </section>

      <p class="small quiet section">
        <a href={~p"/climbs/#{@facts["slug"]}"}>What this Climb measures</a>
        · <a href={~p"/proofs"}>What a finished comparison contains</a>
      </p>
    </Layouts.page>
    """
  end

  defp model_coordinate(model) when is_map(model) do
    [model["provider"], model["model_id"], model["revision"]]
    |> Enum.reject(&(&1 in [nil, ""]))
    |> Enum.join(" · ")
  end

  defp model_coordinate(_model), do: "Not published"

  defp runtime_words(runtime) when is_map(runtime) do
    "A #{runtime["type"]} container, #{runtime["cpu"]} cores, " <>
      "#{runtime["memory_gb"]} GB, #{network_words(runtime["network_policy"])}"
  end

  defp runtime_words(_runtime), do: "Not published"

  defp network_words("restricted"), do: "network restricted to what the tasks need"
  defp network_words("none"), do: "no network access"
  defp network_words(other), do: "network: #{plain(other)}"

  defp scoring_words(%{"primary_reward" => reward, "aggregation" => aggregation}) do
    "#{plain(reward)}, #{plain(aggregation)} across tasks"
  end

  defp scoring_words(_scoring), do: "Not published"

  defp plain(value) when is_binary(value), do: String.replace(value, "_", " ")
  defp plain(value), do: to_string(value)

  defp object_url(digest) when is_binary(digest), do: "/api/v1/objects/" <> digest
  defp object_url(_digest), do: nil

  defp starter_skill_url, do: "/api/v1/objects/" <> StarterSkill.file_digest()
end
