defmodule TechtreeWeb.DocsLive do
  @moduledoc """
  The documentation: a working first run, then the ideas behind it.

  The order is the whole design. A reader arrives wanting to run something, so
  the first thing on the page is the words they hand their agent, then what to
  type if they would rather type it, and then the answer to the question every
  one of those commands raises — what leaves this machine. Concepts come after
  all three, because a concept a reader has already seen working is a different
  thing to read.

  Every command shown here is either read from the published release or is a
  command this build's own command-line tool actually offers. Nothing on this
  page is generated from a help output, and nothing describes a command that
  does not exist. Where a release coordinate belongs, it is rendered from the
  release record this site serves; when that record says its coordinates are
  stand-ins, the page says so instead of printing one.

  The words a reader hands to their agent are not written here. They are the
  same component the installation guide shows, so the two pages cannot drift
  into two different prompts.
  """

  use TechtreeWeb, :live_view

  alias Techtree.Catalog.Query
  import TechtreeWeb.PageCopy, only: [page_copy: 1]

  alias TechtreeWeb.CampaignFacts
  alias TechtreeWeb.InstallComponents
  alias TechtreeWeb.ReleaseInfo

  @impl true
  def mount(_params, _session, socket) do
    campaign = Query.list_climbs() |> List.first()
    release = ReleaseInfo.current()

    {:ok,
     assign(socket,
       page_title: "Docs",
       campaign: campaign,
       campaign_facts: CampaignFacts.for_climb(campaign),
       climb_reference: release && release.introductory_reference,
       instructions: instructions(),
       release: release
     )}
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
              title="Start"
              links={[
                {"What v0.1 is", "#what-this-release-is"},
                {"Quickstart", "#quickstart"},
                {"Install", "#install"},
                {"Run Hello World", "#hello-world"},
                {"What leaves my machine?", "#trust"}
              ]}
            />
            <.docs_group
              title="Concepts"
              links={[
                {"Climbs and Campaigns", "#campaigns"},
                {"Subject and harness", "#subjects"},
                {"Baseline and candidate", "#comparison"},
                {"Taskset validation and the recorded comparison", "#validation"},
                {"Evidence graph", "#evidence-graph"},
                {"Proofs and reproduction", "#proofs"}
              ]}
            />
            <.docs_group
              title="Use Techtree"
              links={[
                {"From the CLI", "#cli"},
                {"From Hermes", "#hermes"},
                {"Traces and local artifacts", "#artifacts"}
              ]}
            />
            <.docs_group
              title="Trust"
              links={[
                {"What leaves my machine?", "#trust"},
                {"What a proof establishes", "#proof-limits"},
                {"Evidence completeness", "#evidence"},
                {"Model pinning", "#model-pinning"}
              ]}
            />
            <.docs_group
              title="Reference"
              links={[
                {"Command reference", "#commands"},
                {"Exit codes", "#exit-codes"},
                {"Configuration and environment variables", "#environment"},
                {"Release coordinates", "#release"},
                {"Troubleshooting", "#troubleshooting"},
                {"Protocol documents", "/protocol"}
              ]}
            />
          </nav>
        </aside>

        <article class="docs-content">
          <header class="docs-hero">
            <div class="docs-hero__top">
              <p class="eyebrow">Techtree v0.1</p>
              <.page_copy />
            </div>
            <h1>Get to a controlled first run.</h1>
            <p class="lede">
              Use the pinned Hermes plugin or install the pinned command-line tool directly.
              Check the machine, obtain the introductory Skill, and prepare the Hello World
              comparison.
            </p>
            <p>
              Preparation does not make model calls. It shows what will run, what may change,
              where model requests go, and the Campaign’s cost limit. Nothing causing LLM
              token spend starts on its own.
            </p>
          </header>

          <.proof_of_concept class="doc-section" />

          <section id="quickstart" class="doc-section">
            <h2>Quickstart</h2>
            <p>Two ways in. Both end at a measured comparison with a receipt.</p>

            <h3>Already running Hermes?</h3>
            <p>Paste one line into your agent:</p>
            <.prompt_block
              id="copy-docs-agent-line"
              label="Give this to your agent"
              text={InstallComponents.agent_line()}
            />

            <h3>No agent yet?</h3>
            <p>
              Paste this into your terminal — it is Nous Research’s own Hermes installer.
              This release names Hermes {minimum(@release, "hermes_version")} as the tested
              host version.
            </p>
            <.prompt_block
              id="copy-docs-hermes-install"
              label="Install the Hermes agent"
              text="curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash"
            />
            <InstallComponents.pinned_commands
              :if={installable?(@release)}
              instructions={@instructions}
            />
            <p :if={not installable?(@release)} class="small quiet">
              The pinned plugin and command-line install commands appear here once an
              installable release is active on this channel.
            </p>

            <h3>What your agent will set up for you</h3>
            <p>
              Handed the line above, the agent reads the pinned guide and takes care of the
              rest: it installs the exact pinned plugin and command-line tool, prepares the
              local layout, checks the machine, installs the evaluation engine, obtains the
              starter Skill, and prepares the Hello World comparison. It asks before it
              installs anything, runs anything, or spends anything — and a trial takes a
              while, so it hands back a run identifier instead of making you wait.
            </p>

            <h3>What you should do yourself</h3>
            <ul class="doc-list">
              <li>Have Python {minimum(@release, "python")}, <code>uv</code>, and Docker
                installed — and Docker running;</li>
              <li>
                sign in to your model-provider account once, so the evaluation can pay for
                its own model calls:
              </li>
            </ul>
            <.command_block
              id="copy-docs-prime-login"
              argv={["prime", "login"]}
              label="Sign in to Prime"
            />
            <ul class="doc-list">
              <li>approve the three moments that matter: installing the plugin, installing
                the command-line tool, and starting the paid comparison;</li>
              <li>read the install-time scan report before confirming, and leave the
                scanning on;</li>
              <li>restart Hermes once, when the agent tells you its tools need loading.</li>
            </ul>

            <h3 id="install">Installing manually</h3>
            <%= if installable?(@release) do %>
              <p>
                This channel is serving a concrete, content-addressed release, so the exact
                command it publishes is the one shown here.
              </p>
              <.command_block
                id="copy-docs-install"
                argv={@release.install_argv}
                label="Install the pinned command-line tool"
              />
              <p class="compatibility">{ReleaseInfo.compatibility(@release)}</p>
            <% else %>
              <p>No installable release is active on this channel yet.</p>
              <p>
                This page prints installation commands only when it is serving a concrete,
                content-addressed release. Techtree never turns stand-in coordinates, branch
                names, or placeholder versions into commands someone could run.
              </p>
              <p>
                Once an installable release is active, its exact CLI and plugin commands will
                appear here from the published release record.
              </p>
            <% end %>

            <p>After installation, the direct terminal flow is:</p>
            <.command_block
              id="copy-docs-setup"
              argv={["techtree", "setup"]}
              label="Prepare the local layout"
            />
            <.command_block
              :if={@climb_reference}
              id="copy-docs-doctor"
              argv={["techtree", "doctor", "--climb", @climb_reference]}
              label="Check this machine"
            />
            <.command_block
              id="copy-docs-skill-starter"
              argv={["techtree", "skill", "starter"]}
              label="Obtain the starter Skill"
            />
            <p>
              <code>techtree skill starter</code>
              verifies and materializes the Skill pinned by the release, then prints the exact
              next command for preparing Hello World. Each later command also prints its next
              valid action.
            </p>
            <p>The direct CLI path does not require a host Hermes installation.</p>
            <p>The Hermes you talk to is an operator. It is not the agent being evaluated.</p>
          </section>

          <section id="hello-world" class="doc-section">
            <h2>What the first run demonstrates</h2>
            <p>Techtree Hello World reduces the experiment to four statements:</p>
            <ol class="steps">
              <li>
                <p class="plain"><strong>Same agent and same tasks.</strong></p>
                <p>
                  Both branches use the same configured model, harness, runtime, task
                  membership, tools, scorer, sampling, and budgets.
                </p>
              </li>
              <li>
                <p class="plain"><strong>The Skill is the only permitted change.</strong></p>
                <p>
                  The baseline mounts no tested Skill. The candidate mounts exactly one
                  content-addressed Skill tree.
                </p>
              </li>
              <li>
                <p class="plain"><strong>Here is the measured difference.</strong></p>
                <p>
                  Prime Intellect’s Verifiers — pinned at version 0.3.1, down to the exact
                  commit — records each task’s outcome and score.
                  Techtree pairs the results and reports the baseline score, candidate score,
                  wins, losses, ties, cost, timing, and validity.
                </p>
              </li>
              <li>
                <p class="plain">
                  <strong>Here is the local receipt and how to verify it.</strong>
                </p>
                <p>
                  Techtree writes a signed, participant-attested proof bundle that can be
                  checked offline.
                </p>
              </li>
            </ol>
            <p>
              Hello World is a synthetic introductory mechanism test. It is not a broad agent
              benchmark and should not be used to make claims about general intelligence or
              production capability.
            </p>
          </section>

          <section id="trust" class="doc-section">
            <h2>What leaves my machine?</h2>
            <p>Techtree sends none of this anywhere on its own:</p>
            <ul class="doc-list">
              <li>Episodes;</li>
              <li>Traces;</li>
              <li>run logs;</li>
              <li>receipts;</li>
              <li>proof bundles; or</li>
              <li>saved Skill proposals.</li>
            </ul>
            <p>
              Publishing a run is the one thing that sends anything, you ask for it a run at
              a time, and what travels is the run’s receipt — the signed report, the
              per-task receipts and the documents they cite. The episodes and traces are
              not in that directory and cannot travel with it.
            </p>
            <p>
              This website has no account system and no route for submitting those artifacts.
            </p>
            <p>
              A comparison still makes real model requests. The baseline and candidate send
              requests to the subject-model provider named by the Campaign, under that
              provider’s policies.
            </p>
            <p>
              When you use the experimental Hermes-guided revision, the verified Skill text
              and a sanitized summary of the run are sent to the model provider configured for
              the host Hermes agent. That may be a different provider from the one used by the
              evaluated subject.
            </p>
            <p>
              The sanitized summary excludes hidden expected answers, grader source, provider
              credentials, private filesystem paths, and the evaluated subject’s final replies.
            </p>
            <p>
              Hello World requires an active Prime CLI login. Techtree does not store, print,
              or copy the provider credential into a draft, run directory, receipt, report, or
              proof bundle.
            </p>
            <p>No Techtree account is required.</p>
          </section>

          <section id="campaigns" class="doc-section">
            <h2>Climbs and Campaigns</h2>
            <p>
              A Climb is the public invitation: its name, version, status, candidate rules,
              and publication policy.
            </p>
            <p>A Campaign is the fixed scientific contract behind the Climb. It defines:</p>
            <ul class="doc-list">
              <li>the exact taskset and ordered task membership;</li>
              <li>the evaluated subject;</li>
              <li>the model and sampling configuration;</li>
              <li>the harness and runtime;</li>
              <li>the scorer;</li>
              <li>the permitted mutation;</li>
              <li>the evidence requirements;</li>
              <li>the execution limits; and</li>
              <li>the data policy.</li>
            </ul>
            <p>
              The Campaign is content-addressed. Changing a scientific field creates a
              different Campaign and a different fingerprint.
            </p>
            <p>Both branches of a comparison are derived from the same Campaign.</p>
            <p :if={@campaign}>
              The introductory Climb is <a href={~p"/climbs/#{@campaign.projection["slug"]}"}>{@campaign.title}</a>. Its
              page shows the public terms and links to the exact published objects behind them.
            </p>
            <p :if={is_nil(@campaign)}>No Climb is published on this channel.</p>
            <p>
              The cost shown before a run is a conservative Campaign limit, not a quoted or
              guaranteed bill. Actual provider-reported or derived cost is recorded separately
              when the run completes.
            </p>
          </section>

          <section id="subjects" class="doc-section">
            <h2>Subject and harness</h2>
            <p>
              The subject is the agent system under evaluation. It is separate from the Hermes
              agent helping you operate Techtree.
            </p>

            <p>
              Both roles are played by Hermes, Nous Research’s open agent — one copy at a
              pinned version inside the experiment, and your own everyday copy outside it,
              on whichever model provider you already use. Scoring belongs to neither:
              Prime Intellect’s Verifiers decides every task’s outcome.
            </p>

            <.comparison_boundary>
              <:side title="Operator">
                <.definition_list>
                  <:fact term="Host Hermes">
                    Tested version: {minimum(@release, "hermes_version")}
                  </:fact>
                  <:fact term="Role">
                    Explains, prepares, asks for approval, and relays Techtree results.
                  </:fact>
                </.definition_list>
              </:side>
              <:side title="Evaluated subject">
                <.definition_list :if={@campaign}>
                  <:fact term="Harness">
                    {@campaign.projection["subject_harness"]} {@campaign.projection[
                      "subject_harness_version"
                    ]}
                  </:fact>
                  <:fact term="Provider">
                    {subject_field(@campaign, "provider")}
                  </:fact>
                  <:fact term="Model">
                    {subject_field(@campaign, "model_id")}
                  </:fact>
                  <:fact term="Runtime">Pinned Docker image</:fact>
                </.definition_list>
                <p :if={is_nil(@campaign)}>No Campaign is published on this channel.</p>
              </:side>
            </.comparison_boundary>

            <p>
              The Campaign pins the subject coordinates. The evaluated subject is not whatever
              Hermes, model, Skill set, or container happens to be installed in the operator’s
              normal session.
            </p>
            <p>
              The host conversation, host memory, ambient plugins, and unrelated host Skills
              are not inherited by the evaluated subject.
            </p>
          </section>

          <section id="comparison" class="doc-section">
            <h2>Baseline and candidate</h2>
            <p>
              Both branches receive the same ordered 36-task membership under the same
              Campaign. For the first Hello World comparison:
            </p>

            <.comparison_boundary>
              <:side title="Baseline">
                <ul class="doc-list">
                  <li>pinned subject</li>
                  <li>no tested Skill</li>
                </ul>
              </:side>
              <:side title="Candidate">
                <ul class="doc-list">
                  <li>same pinned subject</li>
                  <li>one declared starter Skill</li>
                </ul>
              </:side>
            </.comparison_boundary>

            <p>
              Exactly one scientific difference is permitted: the Skill mounted into the
              candidate subject. Techtree checks that rule twice:
            </p>
            <ul class="doc-list">
              <li>before execution, by comparing the resolved run descriptions;</li>
              <li>after execution, by comparing the observed evidence.</li>
            </ul>
            <p>
              An unexplained difference does not become Skill uplift. It makes the comparison
              invalid or changes the type of claim that may be made.
            </p>
            <p>
              Prime Intellect’s Verifiers remains the source of task and score truth.
              Techtree does not calculate a replacement score.
            </p>
          </section>

          <section id="validation" class="doc-section">
            <h2>Taskset validation and the recorded comparison</h2>
            <p>
              Before any tokens are spent, the taskset is checked without asking a model to
              solve it. The published validation receipt establishes, for this taskset, that:
            </p>
            <ul class="doc-list">
              <li>the package loads;</li>
              <li>task identities are unique;</li>
              <li>membership is deterministic;</li>
              <li>each task’s own expected answer scores correctly;</li>
              <li>a known-wrong answer does not;</li>
              <li>the scorer is available; and</li>
              <li>
                required validation work completed without missing tasks or timeouts.
              </li>
            </ul>
            <p :if={CampaignFacts.validation_words(@campaign_facts.validation)}>
              For Hello World, the published receipt reports <strong>{CampaignFacts.validation_words(@campaign_facts.validation)}</strong>.
            </p>
            <p>
              This is mechanical validation. It does not claim that the synthetic tasks are
              economically meaningful, representative of real work, or free from all possible
              model-training contamination.
            </p>

            <h3>There is no held-out final test in v0.1</h3>
            <p>
              Hello World uses one fixed 36-task membership for its recorded comparisons.
            </p>
            <p>
              The baseline and candidate see the same tasks. The experimental guided revision
              also evaluates Skill v1 and Skill v2 on that same membership.
            </p>
            <p>
              Therefore, the guided result is a same-benchmark Skill replacement result. It is
              not a held-out generalization claim.
            </p>
            <p>
              A candidate Skill is frozen and fingerprinted before its comparison starts, but
              v0.1 does not claim that its tasks were hidden from the revision process.
            </p>
          </section>

          <section id="evidence-graph" class="doc-section">
            <h2>Evidence graph</h2>
            <p>
              The graph on this site is an index over published evidence and declared state.
              It is not decorative artwork and it is not a live view into your machine.
            </p>
            <p>A node may represent:</p>
            <ul class="doc-list">
              <li>a published Campaign;</li>
              <li>taskset validation;</li>
              <li>a declared baseline or candidate;</li>
              <li>a completed comparison;</li>
              <li>a signed local receipt; or</li>
              <li>an explicitly unavailable or unexecuted step.</li>
            </ul>
            <p>
              A completed node is shown only when the corresponding published object or
              recorded evidence exists. A declared branch that has not run must say so.
            </p>
            <p>
              This site does not receive your local run artifacts, so it cannot automatically
              add your private runs to the public graph.
            </p>
          </section>

          <section id="proofs" class="doc-section">
            <h2>Proofs and reproduction</h2>
            <p>
              When a comparison finishes, Techtree creates a local proof bundle containing the
              signed comparison report, signed per-task receipts, the resolved, frozen
              description of what will run, membership commitments, and the references needed
              to verify the result from stored bytes.
            </p>
            <p>The bundle is signed with a private key kept on your machine.</p>
            <p>
              You can verify a run ID, a proof-bundle directory, or a signed report file:
            </p>
            <.command_block
              id="copy-docs-proof-verify"
              argv={["techtree", "proof", "verify", "path/to/result-bundle"]}
              label="Verify offline"
            />
            <p>Verification:</p>
            <ul class="doc-list">
              <li>makes no model request;</li>
              <li>contacts no Techtree service;</li>
              <li>fetches nothing from the network; and</li>
              <li>writes nothing to the proof.</li>
            </ul>
            <p>
              A copied bundle can therefore be checked on another machine with the Techtree
              CLI installed.
            </p>
            <p>
              A verified bundle establishes that the stored files, fingerprints, signatures,
              task membership, and reported aggregation agree with one another. It is an
              attestation by the participant-controlled key that produced it.
            </p>
            <p>It does not establish that:</p>
            <ul class="doc-list">
              <li>the participant’s machine behaved honestly;</li>
              <li>an independent party witnessed the computation;</li>
              <li>the result generalizes beyond the Campaign; or</li>
              <li>somebody else reproduced the result.</li>
            </ul>
            <p>
              A reproduction would require another executor to run the same scientific
              contract and record a separately attributable result. v0.1 does not provide a
              public reproduction or attestation-import workflow.
            </p>
            <p>
              Publishing a finished run sends its receipt to the public run log, which is a
              record of what was published and not a reproduction of it. The site checks
              that a receipt is internally consistent and signed; it does not run the
              comparison again and did not watch the original.
            </p>
          </section>

          <section id="cli" class="doc-section">
            <h2>From the CLI</h2>
            <p>
              The CLI is the authoritative local product surface. The Hermes plugin is an
              operator adapter over the CLI’s machine-readable contract, not a second
              evaluation implementation.
            </p>
            <p>Every command group below exists in this build.</p>
            <.definition_list>
              <:fact term="techtree setup">
                Prepare Techtree’s local directory layout, signing identity, and release state.
              </:fact>
              <:fact term="techtree doctor">
                Check whether the machine can run Techtree.
                <span :if={@climb_reference}>
                  Use <code>techtree doctor --climb {@climb_reference}</code>
                  to check the exact subject, credential path, container image, and engine
                  required by Hello World.
                </span>
                Doctor spends no tokens and starts no comparison.
              </:fact>
              <:fact term="techtree climb">
                Browse and enter Climbs: <code>list</code>, <code>show</code>, <code>prepare</code>, <code>start</code>.
              </:fact>
              <:fact term="techtree skill">
                Obtain Skills named by the active release: <code>starter</code>. The starter
                command verifies the Skill against the release digest before keeping it.
              </:fact>
              <:fact term="techtree run">
                Follow and control runs: <code>status</code>, <code>logs</code>, <code>cancel</code>, <code>result</code>. Runs are detached. Closing the terminal
                or ending the initiating Hermes conversation does not end a run.
              </:fact>
              <:fact term="techtree engine">
                Install and check the managed evaluation engine: <code>install</code>, <code>status</code>, <code>verify</code>.
              </:fact>
              <:fact term="techtree proof">
                Check local proofs: <code>verify</code>.
              </:fact>
              <:fact term="techtree release">
                Inspect and verify the release carried by the installed build: <code>info</code>, <code>verify</code>.
              </:fact>
              <:fact term="techtree uplift">
                <span class="state state--development">Experimental</span>
                Skill replacement flow: <code>context</code>, <code>skill-source</code>, <code>prepare</code>, <code>start</code>.
              </:fact>
            </.definition_list>
            <p>
              The CLI exports the sanitized context and verified source Skill, but it does not
              itself call a model to write a revision.
            </p>
            <p>
              A person, Hermes, or another host agent may propose one candidate Skill. Techtree
              then scans it, snapshots it, shows the exact diff, and prepares a Skill-v1-versus-Skill-v2
              comparison.
            </p>
            <p>
              A proposal may be unusable. A valid proposal may improve, tie, or regress.
              Techtree does not automatically retry the proposal.
            </p>

            <h3>Global options</h3>
            <.definition_list>
              <:fact term="--home PATH">
                Use PATH for Techtree’s local state for this invocation.
              </:fact>
              <:fact term="--json">
                Emit exactly one machine-readable envelope on stdout.
              </:fact>
              <:fact term="--no-color">Never use terminal colour in human output.</:fact>
              <:fact term="--no-input">
                Never prompt; fail instead of waiting for a person.
              </:fact>
              <:fact term="--debug">Write additional operational detail to stderr.</:fact>
              <:fact term="--version">Print the installed Techtree version.</:fact>
            </.definition_list>
            <p>Machine mode is designed for agents:</p>
            <ul class="doc-list">
              <li><code>--json</code> implies <code>--no-input</code>;</li>
              <li>machine output contains one JSON object on stdout;</li>
              <li>operational logs go to stderr;</li>
              <li>the command never waits for interactive input.</li>
            </ul>
          </section>

          <section id="hermes" class="doc-section">
            <h2>From Hermes</h2>
            <p>
              The pinned Hermes plugin gives the same local CLI a conversational front door.
            </p>
            <p>The <a href={~p"/start"}>installation guide</a> contains:</p>
            <ul class="doc-list">
              <li>the exact plugin repository and commit;</li>
              <li>the exact CLI version;</li>
              <li>the expected installation commands;</li>
              <li>the prerequisites;</li>
              <li>the privacy boundary; and</li>
              <li>the expected install-time scanner report.</li>
            </ul>
            <p>Hermes must ask before:</p>
            <ol class="steps">
              <li>
                <p class="plain">installing the plugin;</p>
              </li>
              <li>
                <p class="plain">installing the CLI;</p>
              </li>
              <li>
                <p class="plain">starting the first comparison, which spends model tokens;</p>
              </li>
              <li>
                <p class="plain">
                  sending the guided-revision context to a host-model provider; or
                </p>
              </li>
              <li>
                <p class="plain">starting the second comparison, which spends them again.</p>
              </li>
            </ol>
            <p>
              After the plugin is installed and enabled, Hermes must be restarted once so its
              tools load.
            </p>

            <h3>Expected scanner result</h3>
            <p>
              For this release, Hermes is expected to report <code>caution</code>
              with five reviewed findings in three families:
            </p>
            <ul class="doc-list">
              <li>the guard’s own list of command-like words;</li>
              <li>the plugin’s three fixed, shell-free CLI invocation sites; and</li>
              <li>the control-character filter used to sanitize conversational output.</li>
            </ul>
            <p>
              The installation guide explains the findings and points to the exact code. Read
              the report before approving installation. Never turn the scanning off.
            </p>
            <p>
              <strong>Expect Hermes to refuse the first attempt.</strong>
              A community-source plugin at caution is refused rather than queried. It does not
              stop and ask. If the report is the five reviewed findings above and you agree with
              what the named code does, run the same pinned command again with --force appended.
              Hermes’s own help describes <code>--force</code>
              only as
              “Remove existing plugin and reinstall”; overriding this refusal is its second job,
              and it does not switch scanning off.
            </p>
            <p>
              The plugin itself does not score tasks, generate receipts, or implement
              evaluation logic. It invokes fixed CLI argument arrays and reads one JSON
              envelope back.
            </p>

            <h3>Experimental guided revision</h3>
            <p>
              After a completed first comparison, the Hermes flow may offer one experimental
              revision. The model configured for Host Hermes receives:
            </p>
            <ul class="doc-list">
              <li>the verified source Skill;</li>
              <li>the founder-pinned Skill-improver instructions;</li>
              <li>a sanitized summary of the measured run; and</li>
              <li>a strict required response shape.</li>
            </ul>
            <p>
              It does not receive hidden expected answers, grader source, provider credentials,
              local private paths, or the evaluated subject’s final replies.
            </p>
            <p>The host may make exactly one proposal request.</p>
            <p>
              If that request fails, reaches its generation limit, or returns an unusable
              Skill:
            </p>
            <ul class="doc-list">
              <li>the attempt is still used;</li>
              <li>the provider may still charge for it;</li>
              <li>Techtree does not retry automatically.</li>
            </ul>
            <p>When a proposal is usable:</p>
            <ol class="steps">
              <li>
                <p class="plain">the plugin performs preliminary guards;</p>
              </li>
              <li>
                <p class="plain">Techtree runs the ordinary Skill scanner;</p>
              </li>
              <li>
                <p class="plain">Techtree snapshots and fingerprints the proposed Skill;</p>
              </li>
              <li>
                <p class="plain">the exact Skill diff is shown;</p>
              </li>
              <li>
                <p class="plain">the second Campaign and cost limit are shown;</p>
              </li>
              <li>
                <p class="plain">the user must approve again; and</p>
              </li>
              <li>
                <p class="plain">
                  Skill v1 and Skill v2 are evaluated under the same task membership and
                  scientific configuration.
                </p>
              </li>
            </ol>
            <p>
              The second receipt proves only the result of that same-benchmark comparison.
            </p>
          </section>

          <section id="artifacts" class="doc-section">
            <h2>Traces and local artifacts</h2>
            <p>
              Techtree stores local state under its platform-appropriate data directory, or
              under the directory selected with <code>--home</code>.
            </p>
            <p>A run directory may contain:</p>
            <ul class="doc-list">
              <li>the append-only run journal;</li>
              <li>the resolved, frozen description of what will run;</li>
              <li>the evaluation engine’s own recorded outputs;</li>
              <li>operational logs;</li>
              <li>per-task receipts;</li>
              <li>the signed comparison report;</li>
              <li>the execution and cost record;</li>
              <li>the proof bundle; and</li>
              <li>local supervision records.</li>
            </ul>
            <p>
              <code>techtree run result &lt;run-id&gt;</code>
              prints the finished report, and <code>techtree run result &lt;run-id&gt; --json</code>
              returns the same result as one machine-readable envelope.
            </p>
            <p>
              Techtree sends these local artifacts nowhere on its own. Publishing a finished
              run sends its receipt, which carries none of them. Model inference still travels
              to the configured providers as described above.
            </p>
          </section>

          <section id="proof-limits" class="doc-section">
            <h2>What a proof establishes</h2>
            <p>The offline verifier keeps five questions separate.</p>
            <ol class="steps">
              <li>
                <p class="plain"><strong>Cryptographic integrity</strong></p>
                <p>Do the stored files still match their fingerprints and signatures?</p>
              </li>
              <li>
                <p class="plain"><strong>Scientific validity</strong></p>
                <p>
                  Do the documents describe one internally consistent controlled comparison,
                  with the expected task membership and permitted mutation?
                </p>
              </li>
              <li>
                <p class="plain"><strong>Participant attestation</strong></p>
                <p>
                  Which local key vouched for the stored bytes, and what bounded claim does
                  that signature support?
                </p>
              </li>
              <li>
                <p class="plain"><strong>Independent reproduction</strong></p>
                <p>
                  Has a separately attributable executor reproduced this result? For v0.1, the
                  answer is no.
                </p>
              </li>
              <li>
                <p class="plain"><strong>Public publication</strong></p>
                <p>
                  Was the result published? A sealed bundle records that publication had not
                  been requested when it was written, which is not a statement about what
                  happened afterwards. The public run log is where a published run appears.
                </p>
              </li>
            </ol>
            <p>
              A proof that passes these checks is internally consistent and
              participant-attested. It is not proof that the machine was honest or that an
              independent party witnessed the execution.
            </p>
          </section>

          <section id="evidence" class="doc-section">
            <h2>Evidence completeness</h2>
            <p>A Campaign declares which evidence a valid result must contain.</p>
            <p>Missing evidence stays missing:</p>
            <ul class="doc-list">
              <li>a missing task is not treated as zero;</li>
              <li>a missing reward is not guessed;</li>
              <li>a partial comparison is not silently aggregated;</li>
              <li>a missing artifact is not replaced by a placeholder; and</li>
              <li>a failed proof check is not reduced to a warning.</li>
            </ul>
            <p>
              If a required episode does not complete, Techtree does not issue a valid uplift
              claim for that comparison.
            </p>
            <p>
              The website follows the same rule: it does not draw a completed evidence node
              for a document that does not exist.
            </p>
          </section>

          <section id="model-pinning" class="doc-section">
            <h2>Model pinning</h2>
            <p>
              The Campaign pins the provider and model identifier used by the evaluated
              subject.
            </p>
            <p>
              Where a provider publishes an immutable model revision, that revision can also
              be pinned.
            </p>
            <p :if={@campaign}>
              For Hello World, the provider does not publish an immutable revision for <strong>{model_coordinate(@campaign.projection["subject_model"])}</strong>.
            </p>
            <p>
              Both branches use the same configured provider and model identifier, but
              Techtree cannot independently prove that the provider served the same underlying
              model build throughout the comparison.
            </p>
            <p>
              The result therefore carries that limitation as a comparison warning rather than
              hiding it.
            </p>
            <p>
              Participants do not choose a different subject model for one branch. If the
              subject model changed between baseline and candidate, the comparison would
              measure more than the Skill.
            </p>
          </section>

          <section id="commands" class="doc-section">
            <h2>Command reference</h2>
            <p>The command list above is the complete v0.1 CLI namespace.</p>
            <p>For the exact arguments supported by the installed release, use:</p>
            <.command_block
              id="copy-docs-help"
              argv={["techtree", "--help"]}
              label="Every command this build has"
            />
            <p>
              and the same option on one command or group: <code>techtree &lt;command&gt; --help</code>, <code>techtree &lt;group&gt; &lt;command&gt; --help</code>.
            </p>
            <p>
              The installed CLI is authoritative. This page does not document commands that
              might exist in a later release.
            </p>
          </section>

          <section id="exit-codes" class="doc-section">
            <h2>Exit codes</h2>
            <p>
              A host agent may branch on exit codes without parsing human text. Their meanings
              are append-only.
            </p>
            <.definition_list>
              <:fact term="0">Finished as requested.</:fact>
              <:fact term="1">An internal or otherwise unclassified error.</:fact>
              <:fact term="2">The command or its arguments were used incorrectly.</:fact>
              <:fact term="3">Input or stored data failed validation.</:fact>
              <:fact term="4">A prerequisite is missing.</:fact>
              <:fact term="5">The requested object does not exist.</:fact>
              <:fact term="6">The request conflicts with existing immutable state.</:fact>
              <:fact term="7">A credential is missing, expired, or refused.</:fact>
              <:fact term="8">A data or publication policy forbids the request.</:fact>
              <:fact term="9">The managed evaluation engine failed.</:fact>
              <:fact term="10">
                The run failed or the requested run operation is invalid in its current state.
              </:fact>
              <:fact term="11">
                A digest, signature, membership commitment, report, or proof did not verify.
              </:fact>
              <:fact term="130">Cancelled.</:fact>
            </.definition_list>
          </section>

          <section id="environment" class="doc-section">
            <h2>Configuration and environment variables</h2>
            <p>
              Use the global option <code>--home PATH</code>
              to select where a CLI invocation keeps local Techtree state.
            </p>
            <p>The supported <code>TECHTREE_*</code> settings overrides are:</p>
            <.definition_list>
              <:fact term="TECHTREE_OUTPUT_MODE">
                <code>human</code>
                or <code>json</code>. <code>json</code>
                selects machine mode and therefore also disables prompts and colour.
              </:fact>
              <:fact term="TECHTREE_LOG_LEVEL">
                Controls the amount of operational logging.
              </:fact>
              <:fact term="TECHTREE_ACTIVE_ENGINE_DIGEST">
                Selects which installed, content-addressed evaluation engine is active.
              </:fact>
            </.definition_list>
            <p>No other <code>TECHTREE_*</code> setting is inferred or guessed.</p>
            <p>
              <code>TECHTREE_HOME</code>
              is used internally when the CLI starts its detached worker. It is not the
              documented user-facing replacement for <code>--home</code>.
            </p>
            <p>Provider credentials are not Techtree settings. For Hello World, use:</p>
            <.command_block
              id="copy-docs-prime-login-credential"
              argv={["prime", "login"]}
              label="The supported credential path"
            />
            <p>
              An exported <code>PRIME_API_KEY</code>
              in the shell is not the supported detached-run path and is deliberately not
              inherited as ambient worker state.
            </p>
            <p :if={@climb_reference}>
              <code>techtree doctor --climb {@climb_reference}</code>
              checks whether the detached evaluation path can resolve the required credential
              without printing it.
            </p>
          </section>

          <section id="release" class="doc-section">
            <h2>Release coordinates</h2>
            <%= if installable?(@release) do %>
              <p>
                These coordinates are generated from the active release record, not written
                into this page.
              </p>
              <.definition_list>
                <:fact term="Channel">{@release.channel}</:fact>
                <:fact term="CLI version">{@release.version}</:fact>
                <:fact term="CLI source revision">
                  <.digest value={@release.source_revision} />
                </:fact>
                <:fact term="Release record fingerprint">
                  <.digest value={@release.digest} />
                </:fact>
                <:fact :if={@release.repository_url} term="Pinned plugin commit">
                  <a href={@release.repository_url}>{@release.repository_url}</a>
                </:fact>
                <:fact :if={minimum(@release, "hermes_version")} term="Minimum Hermes">
                  {minimum(@release, "hermes_version")}
                </:fact>
                <:fact :if={minimum(@release, "python")} term="Minimum Python">
                  {minimum(@release, "python")}
                </:fact>
                <:fact :if={minimum(@release, "uv")} term="Minimum uv">
                  {minimum(@release, "uv")}
                </:fact>
                <:fact :if={@climb_reference} term="Introductory Climb">
                  {@climb_reference}
                </:fact>
                <:fact :if={starter(@release, "file_digest")} term="Starter Skill file">
                  <.digest value={starter(@release, "file_digest")} />
                </:fact>
                <:fact :if={starter(@release, "tree_digest")} term="Starter Skill tree">
                  <.digest value={starter(@release, "tree_digest")} />
                </:fact>
              </.definition_list>
            <% else %>
              <p>No installable release coordinate is active on this channel yet.</p>
              <p>
                When an installable release is activated, this section is generated from the
                active release record rather than written by hand.
              </p>
            <% end %>

            <p>Do not install from:</p>
            <ul class="doc-list">
              <li><code>main</code>;</li>
              <li><code>latest</code>;</li>
              <li>a shortened commit;</li>
              <li>an unpinned package range;</li>
              <li>a command copied from an old post; or</li>
              <li>a placeholder coordinate.</li>
            </ul>
            <p>The active release record and the installed CLI’s own answers are the authorities:</p>
            <.command_block
              id="copy-docs-release-info"
              argv={["techtree", "release", "info"]}
              label="What release is installed"
            />
            <.command_block
              id="copy-docs-release-verify"
              argv={["techtree", "release", "verify"]}
              label="Check the installed release"
            />
          </section>

          <section id="troubleshooting" class="doc-section">
            <h2>Troubleshooting</h2>
            <p>Start with:</p>
            <.command_block
              :if={@climb_reference}
              id="copy-docs-doctor-troubleshooting"
              argv={["techtree", "doctor", "--climb", @climb_reference]}
              label="Check this machine"
            />
            <p>
              It checks the release, local installation, Prime login, Docker, managed engine,
              subject image, and Climb requirements without spending model tokens.
            </p>
            <p>For the Hermes plugin:</p>
            <.command_block
              id="copy-docs-plugin-doctor"
              argv={["hermes", "plugins", "doctor", "techtree", "--ci"]}
              label="Check the plugin is loaded"
            />
            <p>
              If a run is already in progress: <code>techtree run status &lt;run-id&gt;</code>, <code>techtree run logs &lt;run-id&gt; --tail 200</code>, and <code>techtree run cancel &lt;run-id&gt;</code>.
            </p>
            <p>
              A detached run continues after the initiating terminal or Hermes conversation
              closes. A later session can recover it by run ID.
            </p>
            <p>
              To inspect the result: <code>techtree run result &lt;run-id&gt;</code>. To verify
              its proof: <code>techtree proof verify &lt;run-id&gt;</code>. To check the managed
              engine: <code>techtree engine status</code>
              and <code>techtree engine verify</code>. To check the installed release:
              <code>techtree release info</code>
              and <code>techtree release verify</code>.
            </p>
            <p>When asking for support, include:</p>
            <ul class="doc-list">
              <li>operating system and architecture;</li>
              <li>Hermes version, if using the plugin;</li>
              <li><code>techtree release info --json</code>;</li>
              <li :if={@climb_reference}>
                <code>techtree doctor --climb {@climb_reference} --json</code>;
              </li>
              <li>the stable error code; and</li>
              <li>the run ID, when one exists.</li>
            </ul>
            <p>
              Do not post provider credentials, private Skills, raw Episodes, raw Traces, or
              proof bundles publicly.
            </p>
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

  defp instructions do
    case Query.bootstrap_instructions() do
      {:ok, instructions} -> instructions
      {:error, _error} -> nil
    end
  end

  defp installable?(%{installable?: true}), do: true
  defp installable?(_release), do: false

  defp minimum(%{minimums: minimums}, key), do: minimums[key]
  defp minimum(_release, _key), do: nil

  defp starter(%{starter_skill: starter}, key), do: starter[key]
  defp starter(_release, _key), do: nil

  defp subject_field(%{projection: projection}, key) do
    case projection["subject_model"] do
      model when is_map(model) -> model[key]
      _other -> nil
    end
  end

  defp model_coordinate(model) when is_map(model) do
    [model["provider"], model["model_id"], model["revision"]]
    |> Enum.reject(&(&1 in [nil, ""]))
    |> Enum.join(" · ")
  end

  defp model_coordinate(_model), do: "Not published"
end
