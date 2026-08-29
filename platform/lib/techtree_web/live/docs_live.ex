defmodule TechtreeWeb.DocsLive do
  @moduledoc """
  The operating and integration reference for Techtree.

  Every command shown here is either read from the published release or is a
  command this build's own command-line tool actually offers. Nothing on this
  page is generated from a help output, and nothing describes a command that
  does not exist. Where a release coordinate belongs, it is rendered from the
  release record this site serves; when that record says its coordinates are
  stand-ins, the page says so instead of printing one.
  """

  use TechtreeWeb, :live_view

  alias Techtree.Catalog.Query
  import TechtreeWeb.PageCopy, only: [page_copy: 1]

  alias TechtreeWeb.CampaignFacts
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
              title="Concepts"
              links={[
                {"Climbs and Campaigns", "#campaigns"},
                {"Operator, subject, and scorer", "#subjects"},
                {"Baseline and candidate", "#comparison"},
                {"Taskset validation and the recorded comparison", "#validation"},
                {"Proof bundles", "#proofs"}
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
                {"Troubleshooting", "#troubleshooting"}
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
            <h1>Operate and integrate Techtree.</h1>
            <p class="lede">
              Command reference, runtime behavior, local artifacts, configuration, and
              troubleshooting for the CLI and Hermes plugin.
            </p>
            <p>
              For the claim boundary, read <.link navigate={~p"/proofs"}>Proofs</.link>.
            </p>
          </header>

          <section id="trust" class="doc-section">
            <h2>What leaves my machine?</h2>
            <p>Techtree does not automatically upload your local:</p>
            <ul class="doc-list">
              <li>Episodes;</li>
              <li>Traces;</li>
              <li>run logs;</li>
              <li>receipts;</li>
              <li>proof bundles; or</li>
              <li>saved Skill proposals.</li>
            </ul>
            <p>
              Publishing is a separate, explicit action. It uploads the complete proof bundle —
              its index files, signed report and receipts, cited documents, and any optional
              execution record — while Episodes and Traces remain local. The network returns a
              separate signed publication receipt acknowledging acceptance; it is not the
              uploaded proof bundle.
            </p>
            <p>
              This website has no account system or browser upload form. A finished run is
              published only when you or your operator explicitly invokes the CLI publication
              action.
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
              The sanitized summary excludes hidden expected answers, grader source, private
              environment values, unredacted local paths, and the evaluated subject’s final
              replies.
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
            <h2>Operator, subject, and scorer</h2>
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
              <li>upstream gold and setup validation passed for all 36 tasks;</li>
              <li>two independent inspections produced the same ordered task hashes;</li>
              <li>all task hashes are distinct;</li>
              <li>the ordered hashes match the committed membership;</li>
              <li>the task count is the expected 36; and</li>
              <li>validation recorded no errors, invalid tasks, missing tasks, or timeouts.</li>
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

          <section id="proofs" class="doc-section">
            <h2>Operate the offline verifier</h2>
            <p>
              Use the CLI to verify a completed Result by ID, bundle directory, or signed report.
              The command makes no model request, contacts no Techtree service, and does not
              modify the proof.
            </p>
            <.command_block
              id="copy-docs-proof-verify"
              argv={["techtree", "proof", "verify", "RUN_ID"]}
              label="Verify offline"
            />
            <p>
              <.link navigate={~p"/proofs"}>
                Read what verification does and does not establish.
              </.link>
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
            <p>
              The release coordinates below identify the exact plugin repository and commit
              and the exact CLI version.
            </p>
            <p>Hermes must ask before:</p>
            <ol class="steps">
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
              Read the scanner report and inspect the named code before approving installation.
              Never turn the scanning off.
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
              run uploads the complete proof bundle — its index files, signed report and receipts,
              cited documents, and any optional execution record — while Episodes and Traces
              remain local. The network returns a separate signed publication receipt; it is not
              the uploaded proof bundle. Model inference still travels to the configured
              providers as described above.
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
            <h2>Release integrity</h2>
            <details class="integrity-details">
              <summary>Integrity details</summary>
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
              <p>
                The active release record and the installed CLI’s own answers are the authorities:
              </p>
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
            </details>
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
