defmodule TechtreeWeb.ProofsLive do
  @moduledoc """
  What a finished comparison contains, in the coordinates this release pins.

  This page exists because "view a proof" is the fair question to ask of a
  product that sells proof, and the honest answer in this release has two
  halves. The comparison is real and every coordinate it is pinned to is
  published here, with an address. The result is not: nothing is uploaded to
  this site, nothing is published from it, and so there is no participant's run
  to show. Both halves are on the page, and neither is dressed up as the other.

  What a run adds — the scores, the task-by-task record, the signature — is
  named here as what would be there, never drawn as though it already is.
  """

  use TechtreeWeb, :live_view

  alias Techtree.Catalog.Query
  alias TechtreeWeb.CampaignFacts
  alias TechtreeWeb.ClimbCopy
  alias TechtreeWeb.EvidenceComponents
  alias TechtreeWeb.EvidenceGraph
  alias TechtreeWeb.ReleaseInfo

  @impl true
  def mount(_params, _session, socket) do
    campaign = Query.list_climbs() |> List.first()
    release = ReleaseInfo.current()

    {:ok,
     assign(socket,
       page_title: "A verified run",
       campaign: campaign,
       copy: campaign && ClimbCopy.for_reference(campaign.reference),
       facts: (campaign && campaign.projection) || %{},
       published: CampaignFacts.for_climb(campaign),
       graph: EvidenceGraph.from_climb(campaign, release),
       starter_skill: starter_skill(release)
     )}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page wide>
      <header class="page-heading">
        <p class="eyebrow">Participant-attested</p>
        <h1>A verified run</h1>
        <p class="lede">
          What a finished comparison contains, in the exact coordinates this release
          pins — and what is missing from it until someone runs one.
        </p>
      </header>

      <.warning_callout title="No participant result is published here" attention>
        <p>
          This release publishes nothing and receives nothing. A finished comparison is
          written on the machine that produced it, and stays there unless its
          participant hands the bundle to someone. There is no upload on this site and
          no place to put one.
        </p>
      </.warning_callout>

      <p :if={is_nil(@campaign)} class="empty-state section">
        No campaign is published on this channel, so there are no coordinates to show.
      </p>

      <div :if={@campaign}>
        <EvidenceComponents.graph id="proof-evidence-graph" nodes={@graph} />

        <section class="doc-section">
          <p class="eyebrow">Held fixed</p>
          <h2>The comparison</h2>
          <.definition_list>
            <:fact term="Campaign">
              <a href={~p"/campaigns/#{@facts["slug"]}"}>
                {(@copy && @copy.campaign_title) || @campaign.title}
              </a>
            </:fact>
            <:fact term="Campaign fingerprint">
              <.digest
                value={@facts["campaign_spec_digest"]}
                href={object_url(@facts["campaign_spec_digest"])}
              />
            </:fact>
            <:fact term="Tasks">
              {CampaignFacts.membership_words(@published.membership) || "Not published"}
            </:fact>
            <:fact term="Task validation">
              {CampaignFacts.validation_words(@published.validation) || "Not published"}
            </:fact>
            <:fact term="Harness">
              {@facts["subject_harness"]} {@facts["subject_harness_version"]}
            </:fact>
            <:fact term="Model">{model_coordinate(@facts["subject_model"])}</:fact>
            <:fact term="Scored by">Prime Intellect’s Verifiers, at a pinned version</:fact>
            <:fact term="Ceiling">
              {CampaignFacts.budget_words(@published.budget) || "Not published"}
            </:fact>
          </.definition_list>
        </section>

        <section class="doc-section">
          <p class="eyebrow">The one difference</p>
          <h2>Baseline against candidate</h2>
          <.comparison_boundary>
            <:side title="Baseline">
              <p>No Skill is mounted. Everything else is the campaign above.</p>
            </:side>
            <:side title="Candidate">
              <p>Exactly one Skill is mounted. Nothing else may differ.</p>
              <p :if={@starter_skill} class="small quiet">
                Starts from {@starter_skill["name"]}:
              </p>
              <.digest :if={@starter_skill} value={@starter_skill["tree_digest"]} />
              <p :if={is_nil(@starter_skill)} class="small quiet">
                The Skill is supplied when a participant prepares the run.
              </p>
            </:side>
          </.comparison_boundary>
          <p class="small quiet">
            A revision of that Skill is a second fingerprint, produced and recorded on
            the participant’s own machine. This site never sees either one.
          </p>
        </section>

        <section class="doc-section">
          <p class="eyebrow">What a run adds</p>
          <h2>The parts only a run can carry</h2>
          <.definition_list>
            <:fact term="Score band">
              {(@copy && @copy.starter_note) || "Not published"}
            </:fact>
            <:fact term="Task by task">
              A finished bundle records the outcome of every task in both branches. No
              document this release publishes carries those counts, so none is shown.
            </:fact>
            <:fact term="Signature">
              Produced on the machine that ran the comparison, with a key made there.
            </:fact>
            <:fact term="Reproduction">
              None. A result becomes reproduced when another participant runs the same
              campaign and says what they got; this release offers no way to do that.
            </:fact>
          </.definition_list>
          <p class="small quiet">{publication_note()}</p>
        </section>

        <section class="offline-verify">
          <div>
            <p class="eyebrow">Holding a bundle?</p>
            <h2>Check it on your own machine.</h2>
          </div>
          <.command_block
            id="copy-proof-verify"
            argv={["techtree", "proof", "verify", "path/to/result-bundle"]}
            label="Verify offline"
          />
        </section>

        <p class="small quiet section">
          <a href={~p"/proofs/local"}>What a local result claims</a>
          · <a href={~p"/campaigns/#{@facts["slug"]}"}>The campaign behind it</a>
          · <a href={~p"/docs#proof-limits"}>What verification checks</a>
        </p>
      </div>
    </Layouts.page>
    """
  end

  defp starter_skill(%{starter_skill: %{"name" => name, "tree_digest" => digest} = skill})
       when is_binary(name) and is_binary(digest),
       do: skill

  defp starter_skill(_release), do: nil

  defp model_coordinate(model) when is_map(model) do
    [model["provider"], model["model_id"], model["revision"]]
    |> Enum.reject(&(&1 in [nil, ""]))
    |> Enum.join(" · ")
  end

  defp model_coordinate(_model), do: "Not published"

  defp object_url(digest) when is_binary(digest), do: "/api/v1/objects/" <> digest
  defp object_url(_digest), do: nil
end
