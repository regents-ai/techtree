defmodule TechtreeWeb.HomeLive do
  @moduledoc """
  Why Techtree exists, what a controlled comparison is, what works today, and
  one copyable instruction for getting started.
  """

  use TechtreeWeb, :live_view

  alias Techtree.Catalog.Query
  alias TechtreeWeb.CampaignFacts
  alias TechtreeWeb.Capabilities
  alias TechtreeWeb.ClimbCopy
  alias TechtreeWeb.ReleaseInfo
  alias TechtreeWeb.StartLive

  # Install coordinates come from the published release, never marketing copy.
  @preview_label "Controlled agent evaluations"

  @impl true
  def mount(_params, _session, socket) do
    campaign = Query.list_climbs() |> List.first()

    {:ok,
     assign(socket,
       page_title: nil,
       agent_line: StartLive.instruction(),
       campaign: campaign,
       campaign_copy: campaign && ClimbCopy.for_reference(campaign.reference),
       campaign_facts: CampaignFacts.for_climb(campaign),
       capabilities: Capabilities.all(),
       release: ReleaseInfo.current(),
       preview_label: @preview_label
     )}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page wide flush>
      <section class="hero hero--landing" aria-labelledby="hero-title">
        <div class="hero__stage">
          <div
            id="hero-crown"
            class="hero__optics"
            phx-hook="Optics"
            phx-update="ignore"
            data-optics-kind="crown"
            data-optics-source={~p"/assets/js/crown_island.js"}
            data-optics-pointer="parent"
            aria-hidden="true"
          >
            <canvas id="hero-crown-canvas" class="hero__crown" data-optics-canvas></canvas>
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
                and
                <a class="hero__source-link" href="https://github.com/NousResearch/hermes-agent">Nous&nbsp;Research</a>
              </span>
            </p>
            <.installer release={@release} agent_line={@agent_line} />
            <div class="hero__actions">
              <.link
                id="hero-start"
                class="rg-button rg-button--primary button--primary"
                navigate={~p"/start"}
              >
                <span class="rg-button__label">Choose where to start</span>
              </.link>
              <a class="text-link" href={~p"/results"}>
                View published Results <span aria-hidden="true">→</span>
              </a>
            </div>
          </div>
        </div>

        <a class="hero__more" href="#controlled-comparison" aria-label="How a comparison works">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="m6 5 6 6 6-6" />
            <path d="m6 12 6 6 6-6" />
          </svg>
        </a>
      </section>

      <section
        id="controlled-comparison"
        class="home-section featured"
        aria-labelledby="featured-title"
      >
        <div>
          <p class="eyebrow">A controlled comparison</p>
          <h2 id="featured-title">Only the Skill changes.</h2>
          <p>
            Your agent works the same fixed tasks twice: once without the Skill and once with it.
            The model, the tools and the limits stay the same, so any difference in the results
            comes from the Skill. Techtree calls this a Climb.
          </p>
          <p :if={@campaign}>
            The introductory Climb is <strong>{@campaign.title}</strong>. {(@campaign_copy &&
                                                                              @campaign_copy.scope) ||
              "A fixed comparison that changes one Skill and nothing else."}
          </p>
        </div>
        <dl :if={@campaign} class="featured__facts">
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
        <a :if={@campaign} class="text-link" href={~p"/climbs/#{@campaign.projection["slug"]}"}>
          Inspect the Climb <span aria-hidden="true">→</span>
        </a>
      </section>

      <section id="capabilities" class="home-section" aria-labelledby="capabilities-title">
        <Regent.Structure.section_bar class="section-heading rg-support-band">
          <h2 id="capabilities-title" class="rg-section-bar__label">What works today</h2>
        </Regent.Structure.section_bar>
        <div class="capabilities">
          <div class="capabilities__summary">
            <p>
              Techtree is a working technical preview built from three independent parts:
              <a href="https://github.com/PrimeIntellect-ai/verifiers">Prime Intellect’s Verifiers</a>
              scores the tasks,
              <a href="https://github.com/NousResearch/hermes-agent">Nous Research’s Hermes</a>
              runs the agent, and Techtree runs the comparison and keeps the evidence.
            </p>
            <p :if={@release} class="small quiet">
              Current release: {ReleaseInfo.label(@release)} ·
              <.link navigate={~p"/changelog"}>Changelog</.link>
            </p>
          </div>
          <ul class="capabilities__list">
            <li :for={capability <- @capabilities} class="capabilities__item">
              <span>{capability.name}</span>
              <.capability_status capability={capability.id} />
            </li>
          </ul>
        </div>
      </section>

      <section
        id="from-a-repository"
        class="home-section service-intro"
        aria-labelledby="service-intro-title"
      >
        <Regent.Structure.section_bar>
          <p class="rg-section-bar__label">From a repository</p>
          <.capability_status capability={:repository_tasks} />
        </Regent.Structure.section_bar>
        <div class="service-intro__body">
          <div>
            <h2 id="service-intro-title">Your repo. Tasks from its own history.</h2>
            <p>
              From a local checkout with its history, Techtree finds past fixes whose tests fail
              before the fix and pass after it, and turns each one into a repair task. Every task
              is checked again in a fresh container on your computer, and no model is called.
            </p>
            <p class="service-intro__later">
              <.capability_status capability={:hosted_building} />
              <span>
                The hosted Repo2RLEnv service, which will do this for a pinned repository, comes later.
              </span>
            </p>
            <div class="service-intro__actions">
              <.link navigate={~p"/start#repository"} class="rg-button rg-button--secondary">
                Build tasks from my repository <span aria-hidden="true">→</span>
              </.link>
              <.link navigate={~p"/repo2rlenv"} class="text-link">
                About Repo2RLEnv <span aria-hidden="true">→</span>
              </.link>
            </div>
          </div>
          <ol class="service-flow" aria-label="How tasks are built from your repository">
            <li>
              <span>01 / Source</span><strong>Local checkout</strong><small>Committed history</small>
            </li>
            <li>
              <span>02 / Tasks</span><strong>Past fixes</strong><small>Tests fail before, pass after</small>
            </li>
            <li>
              <span>03 / Check</span><strong>Fresh containers</strong><small>Kept or rejected, with reasons</small>
            </li>
          </ol>
        </div>
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
          <% true -> %>
            <.command_block
              id="copy-home-cli"
              lines={[
                {:command, @release.install_argv},
                {:command, ["techtree", "forge", "inspect-skill", "path/to/your-skill"]}
              ]}
              label="Install, then look at your Skill"
            />
        <% end %>
      </div>
    </div>
    """
  end
end
