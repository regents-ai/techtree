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
  Founder ruling 2026-08-26: this page is deliberately short, and it names its
  own future — publishing a finished run to it arrives in a later release.
  """

  use TechtreeWeb, :live_view

  alias Techtree.Catalog.Query
  alias TechtreeWeb.CampaignFacts
  alias TechtreeWeb.ClimbCopy
  alias TechtreeWeb.EvidenceComponents
  alias TechtreeWeb.ExampleResult
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
       starter_skill: starter_skill(release),
       example:
         ExampleResult.for_campaign(campaign && campaign.projection["campaign_spec_digest"])
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
          Your agent runs one Skill versus another in a <.verifiers_term code />
          environment. The output is a verified result proof that can be shared, and
          used to hill-climb Skill improvement.
        </p>
      </header>

      <section :if={@example} class="example-result" aria-labelledby="example-title">
        <p class="eyebrow">Participant-attested · certified {@example.certified_on}</p>
        <h2 id="example-title">Example Baseline vs. Instructional Skill</h2>
        <p>
          The results shown here are for the v0.1 release, proving that a Hermes agent
          can run long-horizon tasks using the Techtree Plugin, and create <.verifiers_term code />
          proofs of Skill uplift.
        </p>
        <.definition_list>
          <:fact term="Without the Skill">
            {@example.baseline_total} of {@example.tasks} tasks
          </:fact>
          <:fact term="With the Skill">
            {@example.candidate_total} of {@example.tasks} tasks
          </:fact>
          <:fact term="Task by task">
            {@example.wins} wins · {@example.ties} ties · {@example.losses} losses
          </:fact>
          <:fact term="Decision">{@example.decision}</:fact>
          <:fact term="Signed report">
            <.digest value={@example.file_digest} />
          </:fact>
        </.definition_list>
        <p class="small quiet">
          Measured on the founder's machine during v0.1 certification, run {@example.run_id}. Publishing your own result here arrives in a later
          release.
        </p>
      </section>

      <.warning_callout
        :if={is_nil(@example)}
        title="No participant result is published here"
        attention
      >
        <p>
          This release publishes nothing and receives nothing. A finished run stays on
          the machine that produced it. Publishing one to this page arrives in a later
          release — this page is where it will land.
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
            <:fact term="Fingerprint">
              <.digest
                value={@facts["campaign_spec_digest"]}
                href={object_url(@facts["campaign_spec_digest"])}
              />
            </:fact>
            <:fact term="Tasks">
              {CampaignFacts.membership_words(@published.membership) || "Not published"}
            </:fact>
            <:fact term="Subject">
              {@facts["subject_harness"]} {@facts["subject_harness_version"]} · {model_coordinate(
                @facts["subject_model"]
              )}
            </:fact>
            <:fact term="Scored by">Prime Intellect’s Verifiers, at a pinned version</:fact>
            <:fact term="Ceiling">
              {CampaignFacts.budget_words(@published.budget) || "Not published"}
            </:fact>
            <:fact term="The one change">
              One Skill, mounted in the candidate and absent from the baseline.
              <span :if={@starter_skill}>Starts from {@starter_skill["name"]}:</span>
              <.digest :if={@starter_skill} value={@starter_skill["tree_digest"]} />
            </:fact>
          </.definition_list>
        </section>

        <section class="offline-verify">
          <div>
            <p class="eyebrow">What a run adds</p>
            <h2>Scores, every task’s outcome, and a signed bundle.</h2>
            <p class="small quiet">
              Only a run carries those. The bundle is signed on the machine that
              produced it, and anyone holding a copy can check it on their own
              machine, offline:
            </p>
          </div>
          <.command_block
            id="copy-proof-verify"
            argv={["techtree", "proof", "verify", "path/to/result-bundle"]}
            label="Verify offline"
          />
        </section>

        <p class="small quiet section">
          <a href={~p"/campaigns/#{@facts["slug"]}"}>The campaign behind it</a>
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
