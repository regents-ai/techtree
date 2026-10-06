defmodule TechtreeWeb.HomeLive do
  @moduledoc """
  Who Techtree is for and the three things it builds or upgrades (a Skill, a
  harness, an environment), then AgentWalletBench, what each tool is for, how
  testing a Skill works, a quick look at the Hello World Climb, every published
  Climb, what works today, and one copyable instruction for an agent.
  """

  use TechtreeWeb, :live_view

  alias Techtree.Catalog.Query
  alias Techtree.WalletBench.Catalog, as: WalletCatalog
  alias TechtreeWeb.CampaignFacts
  alias TechtreeWeb.Capabilities
  alias TechtreeWeb.ClimbCopy
  alias TechtreeWeb.ReleaseInfo

  # Install coordinates come from the published release, never marketing copy.
  @preview_label "Controlled agent evaluations"

  @impl true
  def mount(_params, _session, socket) do
    release = ReleaseInfo.current()
    climbs = Query.list_climbs()
    campaign = release && Enum.find(climbs, &(&1.reference == release.introductory_reference))

    {:ok,
     assign(socket,
       page_title: "Build or upgrade a Skill, Harness or Env",
       agent_line: agent_line(),
       campaign: campaign,
       campaign_copy: campaign && ClimbCopy.for_reference(campaign.reference),
       campaign_facts: CampaignFacts.for_climb(campaign),
       climbs: Enum.map(climbs, &{&1, ClimbCopy.for_reference(&1.reference)}),
       capabilities: Capabilities.all(),
       tasksmith: climb_with_slug(climbs, "tasksmith-climb"),
       frontier: climb_with_slug(climbs, "frontier-cs-open-ended-climb"),
       wallet_harnesses: names(WalletCatalog.harness_ids(), &WalletCatalog.harness!/1),
       wallet_tools: names(WalletCatalog.wallet_ids(), &WalletCatalog.wallet!/1),
       release: release,
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
              Techtree is designed for use by agents, with WebMCP.
            </h1>
            <p class="hero__mechanism">
              Humans can use it too, with their agent to read and assist.
            </p>
            <h2 id="hero-choice" class="hero__choice">Do you want to build or upgrade:</h2>
            <nav class="hero__products" aria-labelledby="hero-choice">
              <.link navigate={~p"/start#skill"} class="hero-product hero-product--skill">
                <span>
                  <strong class="hero-product__name">Skill</strong>
                  <span class="hero-product__line">
                    Make practice tasks from a Skill and see whether a change helped.
                  </span>
                </span>
                <span class="hero-product__destination">
                  Test a Skill <span aria-hidden="true">→</span>
                </span>
              </.link>
              <.link navigate={~p"/wallet-bench"} class="hero-product hero-product--harness">
                <span>
                  <strong class="hero-product__name">Harness</strong>
                  <span class="hero-product__line">
                    See how a coding agent handles real setup work, starting with wallets.
                  </span>
                </span>
                <span class="hero-product__destination">
                  Wallet tests <span aria-hidden="true">→</span>
                </span>
              </.link>
              <.link navigate={~p"/repo2rlenv"} class="hero-product hero-product--env">
                <span>
                  <strong class="hero-product__name">Env</strong>
                  <span class="hero-product__line">
                    Turn real code into places where agents can practice.
                  </span>
                </span>
                <span class="hero-product__destination">
                  Repo2RLEnv <span aria-hidden="true">→</span>
                </span>
              </.link>
            </nav>
            <.installer release={@release} agent_line={@agent_line} />
          </div>
        </div>

        <a class="hero__more" href="#wallet-bench" aria-label="About AgentWalletBench">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="m6 5 6 6 6-6" />
            <path d="m6 12 6 6 6-6" />
          </svg>
        </a>
      </section>

      <section id="wallet-bench" class="home-section featured" aria-labelledby="wallet-bench-title">
        <div>
          <p class="eyebrow">AgentWalletBench</p>
          <h2 id="wallet-bench-title">Can a coding agent set up a wallet safely?</h2>
          <p>
            AgentWalletBench gives a coding agent a clean computer and asks it to install a wallet
            tool from the tool’s own page, set up a wallet it controls, say how its keys are kept,
            and prove control with a signature.
          </p>
          <p>
            Everything the agent does is recorded, with secrets blanked before anything is kept. A
            judge model rules on each answer, and the bench checks any address and signature on
            Base itself. Use it to see which agents and wallet tools work together before you
            trust one with money.
          </p>
        </div>
        <dl class="featured__facts">
          <div>
            <dt>Agents</dt>
            <dd>{Enum.join(@wallet_harnesses, ", ")}</dd>
          </div>
          <div>
            <dt>Wallet tools</dt>
            <dd>{Enum.join(@wallet_tools, ", ")}</dd>
          </div>
          <div>
            <dt>Each test</dt>
            <dd>Starts from the same clean computer</dd>
          </div>
        </dl>
        <p class="featured__links">
          <.link navigate={~p"/wallet-bench"} class="text-link">
            See the wallet tests <span aria-hidden="true">→</span>
          </.link>
        </p>
      </section>

      <section id="tools" class="home-section" aria-labelledby="tools-title">
        <Regent.Structure.section_bar class="section-heading rg-support-band">
          <h2 id="tools-title" class="rg-section-bar__label">What each tool is for</h2>
        </Regent.Structure.section_bar>
        <p class="tools__intro">
          Turn know-how and real work into tasks agents can practice on, then see what actually
          helps them.
        </p>
        <ul class="tools-list">
          <li id="tool-skill2env" class="tools-list__item">
            <div class="tools-list__name">
              <h3>Skill2Env</h3>
              <.capability_status capability={:skill_test} />
            </div>
            <div class="tools-list__body">
              <p>
                <strong>What it does.</strong>
                Turns a Skill, the know-how written down for an agent, into a set of practice
                tasks with checks. Techtree reads the Skill without running it, plans tasks with
                you, builds and checks them on your computer, and you accept the final set.
              </p>
              <p>
                <strong>Why.</strong>
                The task set is useful on its own: you can keep it, export it, or hand it to
                someone else to run, whether or not you go on to compare anything.
              </p>
              <p>
                <strong>When to use it.</strong>
                You have a Skill and want to know whether agents follow it, or you want a fixed
                set of tasks to measure each change to it.
              </p>
              <p class="tools-list__links">
                <.link navigate={~p"/start#skill"} class="text-link">
                  Test a Skill <span aria-hidden="true">→</span>
                </.link>
                <a class="text-link" href="https://github.com/NVlabs/Skill2Env">
                  NVIDIA’s Skill2Env <span aria-hidden="true">→</span>
                </a>
              </p>
            </div>
          </li>
          <li id="tool-repo2rlenv" class="tools-list__item">
            <div class="tools-list__name">
              <h3>Repo2RLEnv</h3>
              <.capability_status capability={:hosted_building} />
            </div>
            <div class="tools-list__body">
              <p>
                <strong>What it does.</strong>
                Turns a real repository and its history of fixes into practice environments,
                each one a past problem with a known good answer.
              </p>
              <p>
                <strong>Why.</strong>
                Real bugs that were really fixed make realistic practice, and their own tests
                say whether an agent got it right.
              </p>
              <p>
                <strong>When to use it.</strong>
                Your know-how lives in a codebase rather than a written Skill, or you want agents
                to practice on your own software’s real problems.
              </p>
              <p class="tools-list__links">
                <.link navigate={~p"/repo2rlenv"} class="text-link">
                  About Repo2RLEnv <span aria-hidden="true">→</span>
                </.link>
              </p>
            </div>
          </li>
          <li id="tool-tasksmith" class="tools-list__item">
            <div class="tools-list__name">
              <h3>Tasksmith</h3>
            </div>
            <div class="tools-list__body">
              <p>
                <strong>What it does.</strong>
                The HF ML Tasksmith collection packages real changes to Hugging Face’s
                machine-learning libraries as tasks. Techtree’s Tasksmith Climb uses six of them
                to ask whether adding the Tasksmith Skill solves more.
              </p>
              <p>
                <strong>Why.</strong>
                It is a ready-made test on serious code, so you can see a Skill comparison work
                without building tasks of your own first.
              </p>
              <p>
                <strong>When to use it.</strong>
                You want to try Techtree on realistic machine-learning engineering, or measure
                your own Skill on the same six tasks.
              </p>
              <p class="tools-list__links">
                <a :if={@tasksmith} class="text-link" href={~p"/climbs/tasksmith-climb"}>
                  The Tasksmith Climb <span aria-hidden="true">→</span>
                </a>
                <a
                  class="text-link"
                  href="https://huggingface.co/datasets/FineEnvs/HF_ML_Tasksmith"
                >
                  The collection on Hugging Face <span aria-hidden="true">→</span>
                </a>
              </p>
            </div>
          </li>
          <li id="tool-frontiersmith" class="tools-list__item">
            <div class="tools-list__name">
              <h3>FrontierSmith</h3>
              <.capability_status capability={:frontier_climb} />
            </div>
            <div class="tools-list__body">
              <p>
                <strong>What it does.</strong>
                Writes open-ended programming problems, each with its own checker that scores an
                answer from 0 to 1 rather than simply right or wrong. Techtree’s Frontier-CS
                Climb uses ten problems made with it.
              </p>
              <p>
                <strong>Why.</strong>
                Open-ended problems have no single answer to memorise, so a better score means
                better work, and partial credit shows small gains a pass-or-fail test would miss.
              </p>
              <p>
                <strong>When to use it.</strong>
                Your Skill is about solving hard problems well rather than following steps, and
                you want to see whether it raises the quality of the answers.
              </p>
              <p class="tools-list__links">
                <a
                  :if={@frontier}
                  class="text-link"
                  href={~p"/climbs/frontier-cs-open-ended-climb"}
                >
                  The Frontier-CS Climb <span aria-hidden="true">→</span>
                </a>
                <a class="text-link" href="https://github.com/FrontierCS/FrontierSmith">
                  FrontierSmith <span aria-hidden="true">→</span>
                </a>
              </p>
            </div>
          </li>
        </ul>
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

      <section :if={@climbs != []} id="climbs" class="home-section" aria-labelledby="climbs-title">
        <Regent.Structure.section_bar class="section-heading rg-support-band">
          <h2 id="climbs-title" class="rg-section-bar__label">Published Climbs</h2>
        </Regent.Structure.section_bar>
        <ul class="climb-list">
          <li :for={{climb, copy} <- @climbs} class="climb-list__item">
            <a class="text-link" href={~p"/climbs/#{climb.projection["slug"]}"}>{climb.title}</a>
            <p :if={copy}>{copy.scope}</p>
          </li>
        </ul>
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

  defp names(ids, fetch!), do: ids |> Enum.map(&fetch!.(&1).name) |> Enum.sort()

  defp climb_with_slug(climbs, slug), do: Enum.find(climbs, &(&1.projection["slug"] == slug))

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
                {:command, ["regents", "techtree", "forge", "inspect-skill", "path/to/your-skill"]}
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
