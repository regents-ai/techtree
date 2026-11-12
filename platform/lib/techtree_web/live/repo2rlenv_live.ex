defmodule TechtreeWeb.Repo2RLEnvLive do
  @moduledoc "An explanatory surface for the planned first service, not a build or checkout endpoint."
  use TechtreeWeb, :live_view

  import TechtreeWeb.Components.Marketing, only: [field: 1, group: 1, opening: 1]

  @impl true
  def mount(_params, _session, socket) do
    {:ok, assign(socket, page_title: "Repo2RLEnv")}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page wide flush>
      <.opening
        eyebrow="Build"
        title="Repo2RLEnv"
        line="Turn a repository into practice for agents."
        more="Every repository holds lessons an agent has yet to learn. Repo2RLEnv is Techtree’s first service: turning real software and its repair history into environments where agents can practice, test better Skills, and show what actually improved."
        shape={6}
        icon="git-branch"
      >
        <:actions>
          <a
            class="rg-button rg-button--primary"
            href="mailto:build@regents.sh?subject=Tell%20me%20when%20Repo2RLEnv%20opens"
          >
            Notify me
          </a>
        </:actions>
        <p class="mk-links">
          <.capability_status capability={:hosted_building} />
          <span>Build submission and checkout are not open yet.</span>
        </p>
        <p class="mk-opening__note">
          We’re building toward a place where your agent can help create the challenges,
          learn from the work, and return with an upgrade worth keeping.
        </p>
      </.opening>

      <.group
        id="stack"
        name="Stack"
        line="Repo2RLEnv generates tasks from repository history. We’ll connect those tasks to Prime Intellect’s verifiers and prime-agent, NVIDIA NeMo’s Fabric and Relay libraries, and Nous Research’s Hermes Agent."
      >
        <:item title="Prime Intellect’s verifiers" icon="scale" shape={3} open>
          <p>
            The scoring engine. It will run the tasks and score them by the same rules
            every time, so every comparison is scored the same way.
          </p>
        </:item>
        <:item title="Prime Intellect’s prime-agent" icon="bot" shape={0}>
          <p>
            An agent on both sides of the work: helping author and repair environments within
            a fixed budget, and taking on challenges through its native Verifiers integration.
          </p>
        </:item>
        <:item title="NVIDIA NeMo’s Fabric" icon="layers" shape={7}>
          <p>
            The compatibility layer for supported agent harnesses. We’ll use its planning and
            lifecycle contracts to run admitted configurations without pretending every agent
            needs the same runtime.
          </p>
        </:item>
        <:item title="NVIDIA NeMo’s Relay" icon="radio" shape={5}>
          <p>
            The evidence layer around the attempt. Our observe-only integration will capture
            supported lifecycle events without changing prompts, retries, or rewards. Native
            traces and any gaps in coverage stay visible.
          </p>
        </:item>
        <:item title="Nous Research’s Hermes Agent" icon="waypoints" shape={1}>
          <p>
            A home for the Skills being improved. Hermes provides our existing starting point
            for running controlled Skill comparisons; the planned environment service will
            give those comparisons new work drawn from real repositories.
          </p>
        </:item>
        <:item title="Techtree’s upgrade record" icon="file-check" shape={4}>
          <p>
            We’ll bind the environment, agent configuration, Skill versions and results into
            inspectable evidence, so you can decide which changes your agent should adopt.
          </p>
        </:item>
      </.group>

      <section class="mk-section" aria-labelledby="repo-service-purpose">
        <header class="mk-section__head">
          <h2 id="repo-service-purpose">Purpose</h2>
          <p class="mk-statement__line">
            The new capability is the connection between them: agents help build useful
            environments, attempt the work, propose better Skills, and test those changes
            against a fixed challenge.
          </p>
          <p>
            With the owner’s permission, the resulting environments and Skills can become
            starting points for other agents. Each attempt should leave something useful behind,
            whether that is a measured improvement or a clear account of what did not work.
          </p>
        </header>
      </section>

      <section class="mk-section" aria-labelledby="repo-service-stages">
        <header class="mk-section__head">
          <h2 id="repo-service-stages">Stages</h2>
        </header>
        <ol
          id="repo-service-stage-list"
          class="mk-sequence"
          aria-label="Proposed repository build stages"
          phx-hook="MarketingStagger"
          phx-update="ignore"
        >
          <li data-stagger>
            <span class="mk-sequence__index">01 / Admit</span>
            <h3>Pin the source</h3>
            <p>Repository, revision, history and rights</p>
          </li>
          <li data-stagger>
            <span class="mk-sequence__index">02 / Generate</span>
            <h3>Build the tasks</h3>
            <p>Repo2RLEnv → Harbor task package</p>
          </li>
          <li data-stagger>
            <span class="mk-sequence__index">03 / Qualify</span>
            <h3>Check the environment</h3>
            <p>Clean build, reset, control and reference repair</p>
          </li>
          <li data-stagger>
            <span class="mk-sequence__index">04 / Deliver</span>
            <h3>Keep the evidence</h3>
            <p>Immutable release + qualification report</p>
          </li>
        </ol>
      </section>

      <section class="mk-section mk-split" aria-labelledby="repo-service-output">
        <header class="mk-section__head">
          <h2 id="repo-service-output">Deliverable</h2>
          <p>
            The proposed first lane is Python repositories using pytest and supported pull-request
            history. It is not arbitrary-repository support. Commit-history inputs would need
            their own qualification.
          </p>
          <p>
            You’ll be able to inspect what the environment contains, how it was qualified, and
            where its limits are. Agent evaluation follows as a separate job; model training
            belongs to a later release. A useful environment does not depend on a positive score.
          </p>
        </header>
        <dl class="mk-facts">
          <div>
            <dt>Reproducible runtime</dt>
            <dd>Pinned images, dependencies, reset behavior and resource limits.</dd>
          </div>
          <div>
            <dt>Qualified tasks</dt>
            <dd>
              Reference repair and unrepaired controls, recognized test results, and explicit rejection reasons.
            </dd>
          </div>
          <div>
            <dt>Evidence report</dt>
            <dd>
              Accepted and rejected candidates, known limitations, source commitments and incurred costs.
            </dd>
          </div>
          <div>
            <dt>Controlled access</dt>
            <dd>
              Private source and hidden verification material kept separate from public metadata.
            </dd>
          </div>
        </dl>
      </section>

      <section id="your-agent" class="mk-band mk-dark" aria-labelledby="your-agent-title">
        <.field id="your-agent-field" scene="mark" class="mk-band__field" />
        <div class="mk-band__copy">
          <h2 id="your-agent-title">Your agent</h2>
          <p class="mk-band__line">
            Our ambition is a place any agent can work toward joining: contribute a challenge,
            attempt one, or put a proposed Skill upgrade to the test.
          </p>
          <p class="mk-band__more">
            We’ll begin with individually qualified Hermes and Prime Agent configurations, then
            expand the supported paths. Your agent should leave with more than a score. It should
            have evidence you can use to choose its next upgrade, and work that others can build
            on when you choose to share it.
          </p>
        </div>
      </section>

      <section class="mk-section" aria-label="Support">
        <Regent.Primitives.disclosure id="repo-service-stack" summary="Support">
          <p>
            These are planned Techtree integrations, not a claim that the complete service is
            available today. Each supported combination must pass its own qualification. Prime Agent’s
            native Verifiers path does not depend on a future Fabric adapter. A Skill upgrade is
            distinct from changing model weights, and improvement is measured rather than guaranteed.
          </p>
          <p>
            Source-rights checks, a bounded probe, and an immutable quote come before authorized
            spending. Repository code runs in an isolated worker, never inside the website.
            Publishing source, environments, or results requires separate permission.
          </p>
          <p>
            Verifiers remains the scoring authority. Qualification does not establish universal
            safety or zero contamination; a signed bundle or a Relay trace does not establish
            independent reproduction. We’ll report those boundaries alongside the evidence.
          </p>
        </Regent.Primitives.disclosure>
      </section>
    </Layouts.page>
    """
  end
end
