defmodule TechtreeWeb.HomeLive do
  @moduledoc """
  Why Techtree exists, followed by one copyable instruction for getting started.
  """

  use TechtreeWeb, :live_view

  alias Techtree.Catalog.Query
  alias Techtree.Network.Query, as: NetworkQuery
  alias TechtreeWeb.CampaignFacts
  alias TechtreeWeb.ClimbCopy
  alias TechtreeWeb.EvidenceComponents
  alias TechtreeWeb.EvidenceGraph
  alias TechtreeWeb.ReleaseInfo

  # The milestone this preview is, said once. It is not an install coordinate:
  # the version, the fingerprint and the command all come from the published
  # release below, and none of them is written into this page.
  @preview_label "Techtree v0.1 · development release"

  # This names a stable page and introductory Climb rather than a release
  # coordinate, so it remains safe to hand to an agent as the release moves.
  @agent_line "Go to techtree.sh/start and set up Techtree and run the Hello World Climb."

  @crown_studies [
    %{id: "1", label: "Graze"},
    %{id: "2", label: "Orange"},
    %{id: "3", label: "White"},
    %{id: "4", label: "Titanium"}
  ]
  @crown_actions %{crown_1: "1", crown_2: "2", crown_3: "3", crown_4: "4"}

  @impl true
  def mount(_params, _session, socket) do
    campaign = Query.list_climbs() |> List.first()
    release = ReleaseInfo.current()
    proofs = published_proofs(campaign)
    crown_variant = Map.get(@crown_actions, socket.assigns.live_action, "1")
    crown_study? = Map.has_key?(@crown_actions, socket.assigns.live_action)

    {:ok,
     assign(socket,
       page_title: "Improve a Skill. Prove it worked.",
       agent_line: @agent_line,
       campaign: campaign,
       campaign_copy: campaign && ClimbCopy.for_reference(campaign.reference),
       campaign_facts: CampaignFacts.for_climb(campaign),
       graph: EvidenceGraph.from_climb(campaign, release, proofs),
       release: release,
       preview_label: @preview_label,
       crown_studies: @crown_studies,
       crown_variant: crown_variant,
       crown_study?: crown_study?
     )}
  end

  defp published_proofs(%{projection: %{"campaign_spec_digest" => digest}}),
    do: NetworkQuery.for_campaign(digest)

  defp published_proofs(_campaign), do: []

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page wide flush>
      <section
        class="hero"
        data-hero-stage="loading"
        data-crown-variant={@crown_variant}
        data-crown-theme-controlled={if(@crown_study?, do: "false", else: "true")}
        aria-labelledby="hero-title"
      >
        <div
          id="hero-crown"
          class="hero__optics"
          phx-hook="Optics"
          phx-update="ignore"
          data-optics-kind="crown"
          data-optics-source={~p"/assets/js/crown_island.js"}
          data-optics-pointer="viewport"
          data-crown-variant={@crown_variant}
          data-crown-theme-controlled={if(@crown_study?, do: "false", else: "true")}
          aria-hidden="true"
        >
          <canvas
            id="hero-crown-canvas"
            class="hero__crown"
            data-optics-canvas
            data-crown-variant={@crown_variant}
          >
          </canvas>
        </div>

        <nav :if={@crown_study?} class="crown-studies" aria-label="Crown material studies">
          <span>Material study</span>
          <a
            :for={study <- @crown_studies}
            id={"crown-study-#{study.id}"}
            href={"/crown/#{study.id}"}
            data-crown-study={study.id}
            class={["crown-studies__link", study.id == @crown_variant && "is-active"]}
            aria-current={if(study.id == @crown_variant, do: "page")}
          >
            <b>{study.id}</b> {study.label}
          </a>
        </nav>

        <div class="hero__copy">
          <p class="eyebrow">{@preview_label}</p>
          <h1 id="hero-title" class="hero-title">
            <span class="hero-title__line">Improve a Skill.</span>
            <span class="hero-title__line">Prove it worked.</span>
          </h1>
          <p class="hero__mechanism">
            <span>Same pinned agent. Same fixed tasks. One changed Skill.</span>
            <span>Get a signed local receipt for the difference.</span>
          </p>

          <.installer release={@release} agent_line={@agent_line} />

          <div class="hero__actions">
            <.link class="button button--primary" navigate={~p"/start"}>
              <span class="button__mark" aria-hidden="true"></span> Start your first Climb
            </.link>
            <a class="text-link" href={~p"/results"}>
              View published proofs <span aria-hidden="true">→</span>
            </a>
          </div>
        </div>

        <a
          class="hero__more"
          href="#what-this-release-is"
          aria-label="Continue to the v0.1 release section"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="m6 5 6 6 6-6" />
            <path d="m6 12 6 6 6-6" />
          </svg>
        </a>
      </section>

      <.proof_of_concept
        class="home-section proof-of-concept"
        eyebrow="hermes + prime + nvidia agent stack"
        title="v0.1 release"
        nemo_roadmap
      >
        <EvidenceComponents.graph
          :if={@graph != []}
          id="home-evidence-graph"
          nodes={@graph}
          compact
        />
      </.proof_of_concept>

      <section class="home-section process" aria-labelledby="process-title">
        <div class="section-heading">
          <p class="eyebrow">One controlled difference</p>
          <h2 id="process-title">Run. Improve. Prove.</h2>
        </div>
        <div class="process__steps">
          <article>
            <span>01</span>
            <h3>Run</h3>
            <p>Resolve a pinned campaign and record the baseline.</p>
          </article>
          <article>
            <span>02</span>
            <h3>Improve</h3>
            <p>Change one declared Skill under a fixed budget and validation rule.</p>
          </article>
          <article>
            <span>03</span>
            <h3>Prove</h3>
            <p>Sign the comparison, read the outcome of every task, and check the receipt offline.</p>
          </article>
        </div>
      </section>

      <section :if={@campaign} class="home-section featured" aria-labelledby="featured-title">
        <div>
          <p class="eyebrow">Published by this release</p>
          <h2 id="featured-title">
            {(@campaign_copy && @campaign_copy.campaign_title) || @campaign.title}
          </h2>
          <p>{@campaign.summary}</p>
        </div>
        <dl class="featured__facts">
          <div>
            <dt>Tasks</dt>
            <dd>{CampaignFacts.membership_words(@campaign_facts.membership) || "Not published"}</dd>
          </div>
          <div>
            <dt>Harness</dt>
            <dd>
              {@campaign.projection["subject_harness"]}
              {@campaign.projection["subject_harness_version"]}
            </dd>
          </div>
          <div>
            <dt>Checked</dt>
            <dd>{CampaignFacts.validation_words(@campaign_facts.validation) || "Not published"}</dd>
          </div>
        </dl>
        <a class="text-link" href={~p"/climbs/#{@campaign.projection["slug"]}"}>
          Inspect the Climb <span aria-hidden="true">→</span>
        </a>
      </section>

      <section class="home-section trust" aria-labelledby="trust-title">
        <div class="section-heading">
          <p class="eyebrow">Where the work goes</p>
          <h2 id="trust-title">Your work stays local.</h2>
        </div>
        <div class="trust__grid">
          <p>
            Techtree uploads nothing unless you publish a finished run yourself. Publishing
            uploads the complete proof bundle — its index files, signed report and receipts,
            cited documents, and any optional execution record — while Episodes and Traces
            remain local. The network returns a separate signed publication receipt
            acknowledging acceptance; it is not the uploaded proof bundle. The
            agent under test makes real model calls, and those go to the model provider
            you selected, under that provider’s policies.
          </p>
          <p>
            A result signed on your machine is internally consistent and attested by the
            participant who produced it. Nobody else watched the run, and this site never
            receives it.
          </p>
          <p class="trust__stack">
            The agent inside the experiment is Hermes, Nous Research’s open agent, at a
            pinned version. Every task is scored by Prime Intellect’s
            <.verifiers_term label="Verifiers" />, pinned
            just as exactly. Techtree fixes the conditions and signs the comparison.
          </p>
        </div>
        <p class="trust__links">
          <a href={~p"/docs#trust"}>What leaves my machine?</a>
          <span aria-hidden="true">·</span>
          <a href={~p"/proofs/local"}>What a local result claims</a>
        </p>
      </section>
    </Layouts.page>
    """
  end

  attr :release, :map, default: nil
  attr :agent_line, :string, required: true

  defp installer(assigns) do
    ~H"""
    <div class="installer">
      <.prompt_block id="copy-home-agent-line" label="Give this to your agent" text={@agent_line} />

      <p class="installer__divider"><span>Or use the CLI directly</span></p>

      <div class="installer__manual">
        <%= cond do %>
          <% is_nil(@release) -> %>
            <p class="release-state">No release is published on this channel yet.</p>
          <% not @release.installable? -> %>
            <p class="release-state">
              This channel publishes stand-in coordinates, so there is no command to copy yet.
            </p>
          <% @release.introductory_reference -> %>
            <.command_block
              id="copy-home-cli"
              lines={[
                {:command, @release.install_argv},
                {:comment, "Doctor checks prerequisites and prints the exact next action."},
                {:command, ["techtree", "doctor", "--climb", @release.introductory_reference]}
              ]}
              label="Install, then check this machine"
            />
            <p class="installer__doctor-note">
              These commands do not start paid model inference.
            </p>
            <p class="compatibility">{hero_compatibility(@release)}</p>
            <p class="release-coordinate">
              <span>{ReleaseInfo.label(@release)}</span>
              <a href={~p"/docs#release"}>Release details</a>
            </p>
          <% true -> %>
            <p class="release-state">This release does not name an introductory Climb.</p>
        <% end %>
      </div>
    </div>
    """
  end

  defp hero_compatibility(%{minimums: minimums}) do
    [
      "macOS or Linux",
      "uv required",
      if(minimums["docker_required"], do: "Docker required"),
      minimums["python"] && "Python #{minimums["python"]} managed by uv",
      minimums["hermes_version"] &&
        "Hermes #{minimums["hermes_version"]}+ only for the plugin path"
    ]
    |> Enum.reject(&is_nil/1)
    |> Enum.join(" · ")
  end
end
