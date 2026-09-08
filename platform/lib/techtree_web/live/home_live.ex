defmodule TechtreeWeb.HomeLive do
  @moduledoc """
  Why Techtree exists, followed by one copyable instruction for getting started.
  """

  use TechtreeWeb, :live_view

  alias Techtree.Catalog.Query
  alias TechtreeWeb.CampaignFacts
  alias TechtreeWeb.ClimbCopy
  alias TechtreeWeb.ReleaseInfo

  # Install coordinates come from the published release, never marketing copy.
  @preview_label "Controlled agent evaluations"

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
    crown_variant = Map.get(@crown_actions, socket.assigns.live_action, "1")
    crown_study? = Map.has_key?(@crown_actions, socket.assigns.live_action)

    {:ok,
     assign(socket,
       page_title: "Improve a Skill. Prove it worked.",
       agent_line: @agent_line,
       campaign: campaign,
       campaign_copy: campaign && ClimbCopy.for_reference(campaign.reference),
       campaign_facts: CampaignFacts.for_climb(campaign),
       release: release,
       preview_label: @preview_label,
       crown_studies: @crown_studies,
       crown_variant: crown_variant,
       crown_study?: crown_study?
     )}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page wide flush>
      <section
        class="hero hero--landing"
        data-crown-variant={@crown_variant}
        data-crown-theme-controlled={if(@crown_study?, do: "false", else: "true")}
        aria-labelledby="hero-title"
      >
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

        <div class="hero__stage">
          <div
            id="hero-crown"
            class="hero__optics"
            phx-hook="Optics"
            phx-update="ignore"
            data-optics-kind="crown"
            data-optics-source={~p"/assets/js/crown_island.js"}
            data-optics-pointer="parent"
            data-crown-variant={@crown_variant}
            data-crown-theme-controlled={if(@crown_study?, do: "false", else: "true")}
            aria-hidden="true"
          >
            <canvas
              id="hero-crown-canvas"
              class="hero__crown"
              data-optics-canvas
              data-crown-variant={@crown_variant}
            ></canvas>
          </div>

          <div class="hero__copy">
            <p class="eyebrow">{@preview_label}</p>
            <h1 id="hero-title" class="hero-title">
              <span class="hero-title__line">Improve a Skill.</span>
              <span class="hero-title__line">Prove it worked.</span>
            </h1>
            <p class="hero__mechanism">
              <span>Same agent. Same tasks. One Skill upgraded.</span>
              <span>
                Built on
                <a class="hero__source-link" href="https://github.com/PrimeIntellect-ai/verifiers">Prime Intellect</a>
                and <a class="hero__source-link" href="https://github.com/NVIDIA/NeMo-Relay">NVIDIA&nbsp;NeMo</a>.
              </span>
            </p>
            <.installer release={@release} agent_line={@agent_line} />
            <div class="hero__actions">
              <.link
                id="hero-start"
                class="rg-button rg-button--primary button--primary"
                navigate={~p"/start"}
              >
                <span class="rg-button__label">Start your first Climb</span>
              </.link>
              <a class="text-link" href={~p"/results"}>
                View published Results <span aria-hidden="true">→</span>
              </a>
            </div>
          </div>
        </div>

        <a
          class="hero__more"
          href="#first-service"
          aria-label="Explore Techtree’s first planned service"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="m6 5 6 6 6-6" />
            <path d="m6 12 6 6 6-6" />
          </svg>
        </a>
      </section>

      <section
        id="first-service"
        class="home-section service-intro"
        aria-labelledby="service-intro-title"
      >
        <Regent.Structure.section_bar>
          <p class="rg-section-bar__label">First service</p>
          <Regent.Primitives.status>Planned</Regent.Primitives.status>
        </Regent.Structure.section_bar>
        <div class="service-intro__body">
          <div>
            <h2 id="service-intro-title">Your repo. A repeatable environment.</h2>
            <p>
              Repo2RLEnv will turn a pinned repository into a reproducible reinforcement-learning
              environment: buildable runtime, bounded tasks, a scorer, and an evidence report.
            </p>
            <.link navigate={~p"/repo2rlenv"} class="rg-button rg-button--secondary">
              Explore Repo2RLEnv <span aria-hidden="true">→</span>
            </.link>
          </div>
          <ol class="service-flow" aria-label="Planned Repo2RLEnv workflow">
            <li>
              <span>01 / Source</span><strong>Pinned repository</strong><small>Commit + rights</small>
            </li>
            <li>
              <span>02 / Build</span><strong>RL environment</strong><small>Runtime + tasks + scorer</small>
            </li>
            <li>
              <span>03 / Evidence</span><strong>Validation report</strong><small>What passed. What did not.</small>
            </li>
          </ol>
        </div>
      </section>

      <.proof_of_concept
        class="home-section proof-of-concept"
        eyebrow="hermes + prime + nvidia agent stack"
        title="v0.1 release"
        nemo_roadmap
      />

      <section :if={@campaign} class="home-section featured" aria-labelledby="featured-title">
        <div>
          <p class="eyebrow">Introductory Climb</p>
          <h2 id="featured-title">{@campaign.title}</h2>
          <p>
            {(@campaign_copy && @campaign_copy.scope) ||
              "A fixed comparison that changes one Skill and nothing else."}
          </p>
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
        <p class="trust__summary">
          Techtree does not observe the Run. Your work stays local unless you choose to publish
          the finished Result bundle. Model calls still go to the provider selected by the Climb,
          under that provider’s policies.
        </p>
        <p class="trust__links">
          <a href={~p"/verify"}>What verification establishes <span aria-hidden="true">→</span></a>
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
                {:command, ["techtree", "doctor", "--climb", @release.introductory_reference]}
              ]}
              label="Install, then check this machine"
            />
          <% true -> %>
            <p class="release-state">This release does not name an introductory Climb.</p>
        <% end %>
      </div>
    </div>
    """
  end
end
