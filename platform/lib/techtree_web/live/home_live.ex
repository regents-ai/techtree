defmodule TechtreeWeb.HomeLive do
  @moduledoc """
  Why Techtree exists, followed by one copyable instruction for getting started.
  """

  use TechtreeWeb, :live_view

  alias Techtree.Catalog.Query
  alias TechtreeWeb.CampaignFacts
  alias TechtreeWeb.ClimbCopy
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
        class="hero"
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
            <span>Opinionated Stack for Agent Skill Uplift.</span>
            <span>Built on Prime Intellect and NVIDIA NeMo.</span>
          </p>

          <.installer release={@release} agent_line={@agent_line} />

          <div class="hero__actions">
            <.link class="button button--primary" navigate={~p"/start"}>
              <span class="button__mark" aria-hidden="true"></span> Start your first Climb
            </.link>
            <a class="text-link" href={~p"/results"}>
              View published Results <span aria-hidden="true">→</span>
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
          <a href={~p"/proofs"}>What verification establishes <span aria-hidden="true">→</span></a>
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
