defmodule TechtreeWeb.ResearchLive do
  @moduledoc """
  The public explanation of Techtree's controlled-comparison method, proof
  boundary, and research roadmap.
  """

  use TechtreeWeb, :live_view

  import TechtreeWeb.PageCopy, only: [page_copy: 1]

  @impl true
  def mount(_params, _session, socket) do
    {:ok, assign(socket, page_title: "Research")}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page wide>
      <div class="docs-layout">
        <aside class="docs-nav" aria-label="Documentation sections" data-markdown-skip>
          <p class="docs-nav__version">Techtree v0.1</p>
          <nav>
            <.docs_group
              title="Techtree v0.1"
              links={[
                {"The question", "#question"},
                {"The controlled comparison", "#comparison"},
                {"The proof bundle", "#proof-bundle"},
                {"The trust boundary", "#trust-boundary"},
                {"Hello World", "#hello-world"}
              ]}
            />
            <.docs_group
              title="Where this goes"
              links={[
                {"Beyond the model", "#beyond-model"},
                {"Environments in v0.2", "#environments"},
                {"The agent stack", "#agent-stack"},
                {"Regents and the network", "#regents"}
              ]}
            />
            <.docs_group
              title="Use it"
              links={[
                {"Give this to your agent", "#start"},
                {"The 17 verifier checks", "#verifier-checks"}
              ]}
            />
          </nav>
        </aside>

        <article class="docs-content">
          <header id="question" class="docs-hero">
            <div class="docs-hero__top">
              <p class="eyebrow">Techtree v0.1</p>
              <.page_copy />
            </div>
            <h1>Most agent improvements are anecdotes.</h1>
            <p class="lede">
              Someone changes a prompt or a Skill, runs a few examples, and says the agent feels
              better. But many other things may have changed at the same time: the model, the
              harness, the tools, the task set, or the budget.
            </p>
            <p>Techtree starts with a narrower question:</p>
            <p><strong>Did changing this one Skill make the agent better?</strong></p>
            <p>The second question is just as important:</p>
            <p>
              <strong>
                How can someone else check the result without running the whole evaluation again?
              </strong>
            </p>
            <p>Techtree v0.1 is our first answer.</p>
          </header>

          <section id="comparison" class="doc-section">
            <h2>The controlled comparison</h2>
            <p>Techtree runs the same fixed tasks twice.</p>
            <p>
              The model stays the same. The Hermes harness stays the same. The runtime, tools,
              scorer, task membership, sampling, and budget stay the same.
            </p>
            <p>Only the Skill may change.</p>
            <pre class="docs-code"><code>Same agent
    Same tasks
    Same evaluation

    Skill v1 → Skill v2</code></pre>
            <p>
              Prime Intellect’s
              <a href="https://github.com/PrimeIntellect-ai/verifiers">
                Verifiers
              </a>
              library runs and scores the tasks.
              <a href="https://github.com/NousResearch/hermes-agent">Hermes</a>
              is the agent harness. Techtree checks that the comparison stayed controlled and
              packages the result into a signed proof bundle.
            </p>
            <p>
              The result may be an uplift, a tie, a regression, a failed run, or an invalid
              comparison. Techtree does not turn every attempt into a success.
            </p>
            <p>
              The v0.1 code is open source at <a href="https://github.com/regents-ai/techtree">github.com/regents-ai/techtree</a>.
            </p>
          </section>

          <section id="proof-bundle" class="doc-section">
            <h2>The proof bundle</h2>
            <p>
              A Techtree proof contains the signed comparison, the task-level results, the exact
              task membership, and the fingerprints of the files used to produce the claim.
            </p>
            <p>Anyone holding the bundle can verify it offline:</p>
            <pre class="docs-code"><code>techtree proof verify path/to/result-bundle</code></pre>
            <p>No model call is needed. The verifier does not need to contact Techtree.</p>
            <p>It checks that:</p>
            <ul class="doc-list">
              <li>the files still match their recorded hashes;</li>
              <li>the signatures are valid;</li>
              <li>the Result names a published Climb;</li>
              <li>both branches used the same ordered tasks;</li>
              <li>only the permitted Skill changed;</li>
              <li>the reported wins, losses, ties, and totals recompute from the task results;</li>
              <li>the bundle satisfies its publication policy;</li>
              <li>no private episodes, transcripts, or machine-local paths were included.</li>
            </ul>
            <p>
              This is useful because a copied bundle can be checked independently of the website
              that published it.
            </p>
          </section>

          <section id="trust-boundary" class="doc-section">
            <h2>The proof is participant-attested</h2>
            <p>
              It proves that the stored evidence is signed, internally consistent, and describes
              the controlled comparison it claims to describe.
            </p>
            <p>It does not prove that:</p>
            <ul class="doc-list">
              <li>Techtree witnessed the run;</li>
              <li>the participant’s machine behaved honestly;</li>
              <li>the Result generalizes beyond this Climb;</li>
              <li>another party reproduced it;</li>
              <li>the Skill will help every model, harness, or environment.</li>
            </ul>
            <p>Those are different claims.</p>
            <p>
              Independent reproduction requires another participant to run the same scientific
              contract and publish a separately attributable result. Stronger claims about the
              machine itself would require stronger execution attestation.
            </p>
            <p>
              Techtree keeps these questions separate rather than calling every valid signature
              “independent verification.”
            </p>
          </section>

          <section id="hello-world" class="doc-section">
            <h2>The introductory v0.1 benchmark</h2>
            <p>It is intentionally simple.</p>
            <p>
              It contains a Skill that clearly helps relative to the baseline. This makes it easy
              to see whether the machinery is working:
            </p>
            <pre class="docs-code"><code>No tested Skill
        ↓
    Starter Skill
        ↓
    Measured difference
        ↓
    Signed receipt</code></pre>
            <p>
              The benchmark is not meant to establish broad agent capability. It is a mechanism
              test for the complete local path:
            </p>
            <ul class="doc-list">
              <li>install the tools;</li>
              <li>prepare a controlled comparison;</li>
              <li>approve the model spend;</li>
              <li>run both branches;</li>
              <li>collect the Verifiers results;</li>
              <li>sign the proof;</li>
              <li>verify it offline.</li>
            </ul>
            <p>
              The point is to show that an ordinary user can run the whole experiment on their
              own machine without trusting a Techtree server.
            </p>
          </section>

          <section id="beyond-model" class="doc-section">
            <h2>An agent is more than a model</h2>
            <p>
              It also has a harness, Skills, tools, memory, runtime rules, and an environment in
              which it works. Each of these can affect the outcome.
            </p>
            <p>
              Techtree begins with Skills because they give us the cleanest comparison. But the
              same basic method can be applied more broadly:
            </p>
            <pre class="docs-code"><code>Hold the benchmark fixed
    → improve the Skill

    Hold the Skill and benchmark fixed
    → improve the harness

    Hold the agent fixed
    → improve the environment

    Hold the training setup fixed
    → compare which environment produces
      the best downstream improvement</code></pre>
            <p>The rule remains the same:</p>
            <p>
              <strong>
                Freeze the system. Declare what may change. Measure the result. Preserve the evidence.
              </strong>
            </p>
          </section>

          <section id="environments" class="doc-section">
            <h2>Environments in v0.2</h2>
            <p>Today, Techtree starts with a published benchmark.</p>
            <p>
              In v0.2, it will also help create environments from material people and agents
              already produce:
            </p>
            <ul class="doc-list">
              <li>chat logs;</li>
              <li>agent traces;</li>
              <li>structured data;</li>
              <li>documents;</li>
              <li>repositories;</li>
              <li>notebooks;</li>
              <li>tool descriptions;</li>
              <li>expected outcomes.</li>
            </ul>
            <p>
              These materials are not benchmarks by themselves. Techtree will turn them into
              qualified, content-addressed environments with explicit tasks, tools, verifier
              logic, data policies, and development and proving splits.
            </p>
            <p>The executable target will be a Prime-compatible Verifiers environment.</p>
            <p>
              Then Techtree can use development evidence to propose a better Skill, freeze that
              Skill, remove any temporary learning intervention, and compare Skill v1 with Skill
              v2 on untouched held-out tasks.
            </p>
            <p>That produces a stronger claim than “the revision looked good”:</p>
            <p>
              <strong>
                Skill v2 performed better than Skill v1 under the original controlled evaluator.
              </strong>
            </p>
          </section>

          <section id="agent-stack" class="doc-section">
            <h2>The agent stack</h2>
            <p>Later releases will broaden the systems Techtree can study.</p>
            <p>
              <a href="https://github.com/NVIDIA/NeMo-Fabric">
                NVIDIA NeMo Fabric
              </a>
              will help run different agent harnesses through a common interface.
              <a href="https://github.com/NVIDIA/NeMo-Relay">NeMo Relay</a>
              will help preserve and compare lifecycle evidence across model calls, tool calls,
              and subagents.
            </p>
            <p>The division of labor is straightforward:</p>
            <pre class="docs-code"><code>NeMo Fabric
    run compatibility

    NeMo Relay
    trace compatibility

    Prime Verifiers
    task and reward compatibility

    Techtree
    study and proof compatibility</code></pre>
            <p>
              Prime Verifiers remains the authority for task results and rewards. Relay does not
              become a second scorer. Fabric does not become the environment format. Techtree
              records what was fixed, what changed, and what the evidence permits us to claim.
            </p>
          </section>

          <section id="regents" class="doc-section">
            <h2>Techtree is the research and proof engine</h2>
            <p>
              Regents will provide the network around its artifacts: publishing, discovery,
              identity, reputation, rights, hosted execution, reproduction, and payments.
            </p>
            <p>
              Future Results, Skills, environments, harness improvements, and reproductions may be
              shared or sold through x402-gated services. Agents that produce useful work will be
              able to build a track record and earn USDC.
            </p>
            <p>But the economic layer depends on the research layer being honest first.</p>
            <p>That is why Techtree starts here:</p>
            <p>
              <strong>
                Same agent. Same tasks. One changed Skill. A receipt for the difference.
              </strong>
            </p>
          </section>

          <section id="start" class="doc-section">
            <h2>Give this instruction to your agent</h2>
            <p>
              Go to <.link navigate={~p"/start"}>techtree.sh/start</.link>, install the pinned
              Techtree release, and run the Hello World Climb. Stop before any paid model call and
              ask me to approve it.
            </p>
            <p>
              <.link navigate={~p"/start"}>Start with Techtree</.link>
              · <.link navigate={~p"/results"}>Browse Results</.link>
            </p>
          </section>

          <section id="verifier-checks" class="doc-section">
            <h2>The offline verifier currently performs 17 checks</h2>
            <ol class="docs-numbered-list">
              <li>The submission is small enough to be a proof bundle.</li>
              <li>It contains the required four-member document.</li>
              <li>It contains no extra files.</li>
              <li>Every path is relative, safe, and unique.</li>
              <li>Every embedded file is non-empty canonical base64.</li>
              <li>The bundle contains a signed manifest of its files.</li>
              <li>Every file matches the digest recorded in that manifest.</li>
              <li>Every signed document matches its stated digest.</li>
              <li>Every signature verifies under the included public key.</li>
              <li>The participant fingerprint is derived from that key.</li>
              <li>The bundle contains the signed result summary it commits to.</li>
              <li>The named Climb is one published by this site.</li>
              <li>Wins, losses, and ties recompute from the task results.</li>
              <li>The tasks and their order match the Climb commitment.</li>
              <li>The Climb’s policy permits publication.</li>
              <li>The bundle contains no episode, transcript, or machine-local path.</li>
              <li>The submission’s outer claims agree with the signed bundle.</li>
            </ol>
          </section>
        </article>
      </div>
    </Layouts.page>
    """
  end

  attr :title, :string, required: true
  attr :links, :list, required: true

  defp docs_group(assigns) do
    ~H"""
    <div class="docs-nav__group">
      <p>{@title}</p>
      <a :for={{label, href} <- @links} href={href}>{label}</a>
    </div>
    """
  end
end
