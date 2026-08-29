defmodule TechtreeWeb.ProofsLive do
  @moduledoc """
  What a finished comparison contains, in the coordinates this release pins.

  The page shows one real certification comparison, the complete evidence graph,
  the conditions held fixed, and the command for checking a Result offline.
  """

  use TechtreeWeb, :live_view

  alias Techtree.Catalog.Query
  alias TechtreeWeb.CampaignFacts
  alias TechtreeWeb.ClimbCopy
  alias TechtreeWeb.EvidenceComponents
  alias TechtreeWeb.EvidenceGraph
  alias TechtreeWeb.ExampleResult
  alias TechtreeWeb.ReleaseInfo

  @impl true
  def mount(_params, _session, socket) do
    campaign = Query.list_climbs() |> List.first()
    release = ReleaseInfo.current()

    {:ok,
     assign(socket,
       page_title: "What verification establishes",
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
        <h1>What verification establishes</h1>
        <p class="lede">
          Inspect one complete comparison, what Techtree can verify inside it, and the boundary
          between an internally consistent Result and an independently observed Test.
        </p>
      </header>

      <.proof_of_concept class="doc-section" compact />

      <section class="doc-section">
        <p class="eyebrow">The boundary</p>
        <h2>Verification is not observation.</h2>
        <p>
          A passing bundle is internally consistent and signed by the participant-controlled
          key it names. It does not prove the machine behaved honestly, that an independent
          party watched the Test, that the result generalizes, or that anyone reproduced it.
        </p>
      </section>

      <section :if={@example} class="example-result" aria-labelledby="example-title">
        <p class="eyebrow">Participant-attested · certified {@example.certified_on}</p>
        <h2 id="example-title">Example Baseline vs. Instructional Skill</h2>
        <p>
          One comparison from the v0.1 certification, shown in full. The tasks are
          synthetic and were built to demonstrate the mechanism, so a good score here
          says nothing about how an agent performs on real work, and neither does a
          poor one. Nobody outside this project has reproduced it.
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
          Measured on the founder's machine during v0.1 certification, run {@example.run_id}.
          <a href={~p"/results"}>Browse published Results.</a>
        </p>
      </section>

      <.warning_callout
        :if={is_nil(@example)}
        title="No certification Result is available on this channel"
        attention
      >
        <p>
          A finished run stays on the machine that produced it unless its owner chooses
          to publish it. Published comparisons appear in <.link navigate={~p"/results"}>Results</.link>.
        </p>
      </.warning_callout>

      <p :if={is_nil(@campaign)} class="empty-state section">
        No Climb is published on this channel, so there are no coordinates to show.
      </p>

      <div :if={@campaign}>
        <EvidenceComponents.graph id="proof-evidence-graph" nodes={@graph} />

        <section class="doc-section">
          <p class="eyebrow">Held fixed</p>
          <h2>The comparison</h2>
          <.definition_list>
            <:fact term="Climb">
              <a href={~p"/climbs/#{@facts["slug"]}"}>
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
              machine, offline.
            </p>
          </div>
          <.command_block
            id="copy-proof-verify"
            argv={["techtree", "proof", "verify", "path/to/result-bundle"]}
            label="Verify offline"
          />
        </section>

        <p class="small quiet section">
          <a href={~p"/climbs/#{@facts["slug"]}"}>The Climb behind it</a>
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
