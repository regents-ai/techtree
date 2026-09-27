defmodule TechtreeWeb.HomeLive do
  @moduledoc """
  Why Techtree exists, how testing a Skill works, a quick look at the Hello
  World Climb, what works today, and one copyable instruction for getting
  started.
  """

  use TechtreeWeb, :live_view

  alias Techtree.Catalog.Query
  alias TechtreeWeb.CampaignFacts
  alias TechtreeWeb.Capabilities
  alias TechtreeWeb.ClimbCopy
  alias TechtreeWeb.ReleaseInfo

  # Install coordinates come from the published release, never marketing copy.
  @preview_label "Controlled agent evaluations"

  @impl true
  def mount(_params, _session, socket) do
    campaign = Query.list_climbs() |> List.first()

    {:ok,
     assign(socket,
       page_title: "Improve a Skill. Prove it worked.",
       agent_line: agent_line(),
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
              Run the same tasks with and without your Skill. See what improved, what regressed,
              and keep a report anyone can check.
            </p>
            <.installer release={@release} agent_line={@agent_line} />
            <div class="hero__actions">
              <a class="text-link" href={~p"/examples/tdd"}>
                See a real comparison <span aria-hidden="true">→</span>
              </a>
            </div>
            <p class="hero__terms">
              Runs on your computer · Model calls go to the provider you choose · You approve
              each run first · Publishing is optional
            </p>
          </div>
        </div>

        <a class="hero__more" href="#skill-test" aria-label="How testing a Skill works">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="m6 5 6 6 6-6" />
            <path d="m6 12 6 6 6-6" />
          </svg>
        </a>
      </section>

      <section id="skill-test" class="home-section service-intro" aria-labelledby="skill-test-title">
        <Regent.Structure.section_bar>
          <p class="rg-section-bar__label">Test your Skill</p>
          <.capability_status capability={:skill_test} />
        </Regent.Structure.section_bar>
        <div class="service-intro__body">
          <div>
            <h2 id="skill-test-title">Only the Skill changes.</h2>
            <p>
              Techtree makes practice tasks from what your Skill teaches. Your agent then works
              the same tasks twice: once without the Skill, or with its earlier version, and once
              with it. The model, the tools and the limits stay the same, so any difference comes
              from the Skill.
            </p>
            <p>
              Some tasks are held out from anyone improving the Skill. Their result is the one
              to trust when you ask “should I keep this change?”, because no revision could have
              studied them.
            </p>
            <div class="service-intro__actions">
              <.link navigate={~p"/start#skill"} class="rg-button rg-button--secondary">
                Test your Skill <span aria-hidden="true">→</span>
              </.link>
              <.link navigate={~p"/examples/tdd"} class="text-link">
                See a real comparison <span aria-hidden="true">→</span>
              </.link>
            </div>
          </div>
          <ol class="service-flow" aria-label="How a Skill is tested">
            <li>
              <span>01 / Tasks</span><strong>Made from your Skill</strong><small>You review the plan and keep the tasks that work</small>
            </li>
            <li>
              <span>02 / Compare</span><strong>Run twice</strong><small>Without the Skill or its earlier version, then with it</small>
            </li>
            <li>
              <span>03 / Decide</span><strong>Held-out tasks</strong><small>Improved, regressed, mixed or no difference</small>
            </li>
          </ol>
        </div>
      </section>

      <section id="quick-look" class="home-section featured" aria-labelledby="featured-title">
        <div>
          <p class="eyebrow">A quick look</p>
          <h2 id="featured-title">See how a comparison runs.</h2>
          <p>
            The Hello World Climb ships with every release: a small, fixed set of tasks run once
            without a starter Skill and once with it. It shows how a run is approved, what it
            records and what a Result looks like. Its toy tasks say nothing about your own Skill.
          </p>
          <p :if={@campaign}>
            It is
            <strong>{@campaign.title}</strong><span :if={@campaign_copy}>, {@campaign_copy.introduction}</span>.
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
        <p class="featured__links">
          <.link navigate={~p"/start#example"} class="text-link">
            Try the example <span aria-hidden="true">→</span>
          </.link>
          <a :if={@campaign} class="text-link" href={~p"/climbs/#{@campaign.projection["slug"]}"}>
            Inspect the Climb <span aria-hidden="true">→</span>
          </a>
          <a class="text-link" href={~p"/results"}>
            Published Results <span aria-hidden="true">→</span>
          </a>
        </p>
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
            <p class="later-note later-note--inline">
              <.capability_status capability={:hosted_building} />
              The hosted Repo2RLEnv service, which will do this for a pinned repository, comes later.
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
          Techtree doesn’t watch your runs. Your work stays local unless you choose to publish
          the finished Result bundle. Model calls go to the model provider you run with,
          under that provider’s policies.
        </p>
        <p class="trust__links">
          <a href={~p"/verify"}>What verification establishes <span aria-hidden="true">→</span></a>
        </p>
      </section>
    </Layouts.page>
    """
  end

  @doc """
  The home page's one short line for an agent. The agent guide it points at
  carries the steps and the stops; /start keeps the longer instruction.
  """
  def agent_line do
    "Read #{url(~p"/skill.md")} and help me test one of my Skills with Techtree. " <>
      "Ask me before any paid model call or before publishing anything."
  end

  attr :release, :map, default: nil
  attr :agent_line, :string, required: true

  defp installer(assigns) do
    ~H"""
    <div class="installer">
      <.prompt_block
        id="copy-home-agent-line"
        label="Paste into your agent’s chat"
        text={@agent_line}
        copy_variant="primary"
      />

      <details class="installer__manual">
        <summary>Use the command line instead</summary>
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
        <.link navigate={~p"/start"} class="text-link">
          Every way to start <span aria-hidden="true">→</span>
        </.link>
      </details>
    </div>
    """
  end
end
