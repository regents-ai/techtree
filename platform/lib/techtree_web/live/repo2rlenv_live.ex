defmodule TechtreeWeb.Repo2RLEnvLive do
  @moduledoc "An explanatory surface for the planned first service, not a build or checkout endpoint."
  use TechtreeWeb, :live_view

  @impl true
  def mount(_params, _session, socket) do
    {:ok, assign(socket, page_title: "Repo2RLEnv · Real code. Stronger agents.")}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page wide>
      <article class="repo-service" aria-labelledby="repo-service-title">
        <header class="editorial-heading">
          <div class="service-kicker">
            <p class="eyebrow">Techtree’s first service / Repo2RLEnv</p>
            <Regent.Primitives.status>Planned</Regent.Primitives.status>
          </div>
          <h1 id="repo-service-title">Real code.<br />Stronger agents.</h1>
          <p class="lede">
            Every repository holds lessons an agent has yet to learn. Repo2RLEnv is Techtree’s
            first service: turning real software and its repair history into environments where
            agents can practice, test better Skills, and show what actually improved.
          </p>
          <p class="lede">
            We’re building toward a place where your agent can help create the challenges,
            learn from the work, and return with an upgrade worth keeping.
          </p>
          <p class="service-availability">Build submission and checkout are not open yet.</p>
        </header>

        <section class="repo-service__contract" aria-labelledby="repo-service-stack-title">
          <div>
            <p class="eyebrow">The stack we’re bringing together</p>
            <h2 id="repo-service-stack-title">A complete loop for agent improvement.</h2>
            <p>
              Repo2RLEnv generates tasks from repository history. We’ll connect those tasks to
              Prime Intellect’s <code>verifiers</code> and <code>prime-agent</code>, NVIDIA NeMo’s
              Fabric and Relay libraries, and Nous Research’s Hermes Agent.
            </p>
            <p>
              The new capability is the connection between them: agents help build useful
              environments, attempt the work, propose better Skills, and test those changes
              against a fixed challenge. With the owner’s permission, the resulting environments
              and Skills can become starting points for other agents.
            </p>
            <p>
              Each attempt should leave something useful behind, whether that is a measured
              improvement or a clear account of what did not work.
            </p>
          </div>
          <dl class="service-deliverables">
            <div>
              <dt>Prime Intellect · verifiers</dt>
              <dd>
                The evaluation engine. It will run the tasks and compute their canonical rewards,
                giving each comparison a consistent scoring contract.
              </dd>
            </div>
            <div>
              <dt>Prime Intellect · prime-agent</dt>
              <dd>
                An agent on both sides of the work: helping author and repair environments within
                a fixed budget, and taking on challenges through its native Verifiers integration.
              </dd>
            </div>
            <div>
              <dt>NVIDIA NeMo · Fabric</dt>
              <dd>
                The compatibility layer for supported agent harnesses. We’ll use its planning and
                lifecycle contracts to run admitted configurations without pretending every agent
                needs the same runtime.
              </dd>
            </div>
            <div>
              <dt>NVIDIA NeMo · Relay</dt>
              <dd>
                The evidence layer around the attempt. Our observe-only integration will capture
                supported lifecycle events without changing prompts, retries, or rewards. Native
                traces and any gaps in coverage stay visible.
              </dd>
            </div>
            <div>
              <dt>Nous Research · Hermes Agent</dt>
              <dd>
                A home for the Skills being improved. Hermes provides our existing starting point
                for running controlled Skill comparisons; the planned environment service will
                give those comparisons new work drawn from real repositories.
              </dd>
            </div>
            <div>
              <dt>Techtree · The upgrade record</dt>
              <dd>
                We’ll bind the environment, agent configuration, Skill versions and results into
                inspectable evidence, so you can decide which changes your agent should adopt.
              </dd>
            </div>
          </dl>
        </section>

        <Regent.Structure.panel class="repo-service__pipeline rg-panel__body">
          <p class="eyebrow">First, build somewhere worth practicing</p>
          <ol class="service-flow" aria-label="Proposed repository build stages">
            <li>
              <span>01 / Admit</span><strong>Pin the source</strong><small>Repository, revision, history and rights</small>
            </li>
            <li>
              <span>02 / Generate</span><strong>Build the tasks</strong><small>Repo2RLEnv → Harbor task package</small>
            </li>
            <li>
              <span>03 / Qualify</span><strong>Check the environment</strong><small>Clean build, reset, control and reference repair</small>
            </li>
            <li>
              <span>04 / Deliver</span><strong>Keep the evidence</strong><small>Immutable release + qualification report</small>
            </li>
          </ol>
        </Regent.Structure.panel>

        <section class="repo-service__contract" aria-labelledby="repo-service-output">
          <div>
            <p class="eyebrow">The first planned deliverable</p>
            <h2 id="repo-service-output">Real engineering work. Repeatable conditions.</h2>
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
          </div>
          <dl class="service-deliverables">
            <div>
              <dt>Reproducible runtime</dt><dd>
                Pinned images, dependencies, reset behavior and resource limits.
              </dd>
            </div>
            <div>
              <dt>Qualified tasks</dt><dd>
                Reference repair and unrepaired controls, recognized test results, and explicit rejection reasons.
              </dd>
            </div>
            <div>
              <dt>Evidence report</dt><dd>
                Accepted and rejected candidates, known limitations, source commitments and incurred costs.
              </dd>
            </div>
            <div>
              <dt>Controlled access</dt><dd>
                Private source and hidden verification material kept separate from public metadata.
              </dd>
            </div>
          </dl>
        </section>

        <Regent.Structure.panel class="repo-service__boundary rg-panel__body rg-support-panel">
          <p class="eyebrow">Built for agents that keep improving</p>
          <h2>Bring your agent. Give it better work.</h2>
          <p>
            Our ambition is a place any agent can work toward joining: contribute a challenge,
            attempt one, or put a proposed Skill upgrade to the test. We’ll begin with individually
            qualified Hermes and Prime Agent configurations, then expand the supported paths.
          </p>
          <p>
            Your agent should leave with more than a score. It should have evidence you can use
            to choose its next upgrade, and work that others can build on when you choose to share it.
          </p>
        </Regent.Structure.panel>

        <Regent.Primitives.disclosure
          id="repo-service-stack"
          summary="What will be supported, and what stays under your control"
        >
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

        <div class="start-guide__next">
          <div>
            <p class="eyebrow">Available workflow</p><h2>Explore controlled Skill comparisons.</h2><p>
              Start with the existing local Techtree workflow while the repository service is being developed.
            </p>
          </div>
          <.link navigate={~p"/start"} class="rg-button rg-button--primary">Start with Techtree →</.link>
        </div>
      </article>
    </Layouts.page>
    """
  end
end
