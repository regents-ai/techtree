defmodule TechtreeWeb.DocsLive do
  @moduledoc """
  The concise operating and integration reference for Techtree.

  Commands containing release coordinates are rendered from the active release
  rather than copied into this page.
  """

  use TechtreeWeb, :live_view

  import TechtreeWeb.PageCopy, only: [page_copy: 1]

  alias TechtreeWeb.PublicDocuments
  alias TechtreeWeb.ReleaseInfo
  alias TechtreeWeb.StartLive

  @impl true
  def mount(_params, _session, socket) do
    release = ReleaseInfo.current()

    {:ok,
     assign(socket,
       page_title: "Docs",
       release: release,
       instruction: StartLive.instruction(),
       plugin_commands: plugin_commands(release)
     )}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page wide>
      <div class="docs-layout">
        <aside class="docs-nav" aria-label="Documentation sections" data-markdown-skip>
          <p class="docs-nav__version">
            Techtree{if @release, do: " " <> ReleaseInfo.label(@release)}
          </p>
          <nav>
            <.docs_group
              title="Get started"
              links={[
                {"Install and check", "#install"},
                {"Test your Skill", "#test-skill"},
                {"Compare two versions", "#two-versions"},
                {"Take a quick look", "#first-climb"},
                {"Use Hermes", "#hermes"}
              ]}
            />
            <.docs_group
              title="Results"
              links={[
                {"Verify locally", "#verify"},
                {"Publish a Result", "#publish"}
              ]}
            />
            <.docs_group
              title="CLI"
              links={[
                {"Machine interface", "#integration"},
                {"Browser agents", "#browser-tools"},
                {"Data boundary", "#data-boundary"},
                {"Troubleshooting", "#troubleshooting"}
              ]}
            />
            <.docs_group
              title="API"
              links={[
                {"Errors", "#errors"},
                {"Rate limits", "#rate-limits"},
                {"Versioning", "#versioning"}
              ]}
            />
            <.docs_group
              title="Method"
              links={[
                {"The question", "#method"},
                {"The proof bundle", "#proof-bundle"},
                {"The trust boundary", "#trust-boundary"},
                {"Hello World", "#hello-world"},
                {"Revising a Skill", "#skill-revision"}
              ]}
            />
            <.docs_group
              title="Where this goes"
              links={[
                {"Beyond the model", "#beyond-model"},
                {"Execution portability", "#environments"},
                {"The agent stack", "#agent-stack"},
                {"Regents and the network", "#regents"}
              ]}
            />
            <.docs_group
              title="Use it"
              links={[
                {"Give this to your agent", "#research-start"}
              ]}
            />
          </nav>
        </aside>

        <article class="docs-content" data-markdown-root>
          <header class="docs-hero">
            <div class="docs-hero__top">
              <p class="eyebrow">Operator reference</p>
              <.page_copy />
            </div>
            <h1>Operation Guide and Mechanism Docs</h1>
            <p class="lede">
              Install the released CLI, test a Skill against no Skill or its earlier version,
              verify a Result, and publish a Climb Result to the public Results log.
            </p>
            <p>
              For the info on Prime Intellect’s
              <a href="https://github.com/PrimeIntellect-ai/verifiers"><code>verifiers</code></a>
              mechanism, go to the section <a href="#method">Method.</a>
            </p>
          </header>

          <section id="install" class="doc-section">
            <h2>Install and check this machine</h2>
            <%= cond do %>
              <% is_nil(@release) -> %>
                <p>No release is published on this channel.</p>
              <% not @release.installable? -> %>
                <p>
                  This channel currently publishes stand-in coordinates, not an installable release.
                </p>
              <% @release.introductory_reference -> %>
                <.command_block
                  id="copy-docs-install"
                  lines={[
                    {:command, @release.install_argv},
                    {:command, ["techtree", "doctor", "--climb", @release.introductory_reference]}
                  ]}
                  label="Install, then run Doctor"
                />
                <p class="small quiet">
                  Doctor checks prerequisites and prints the next action. It does not start paid
                  model inference.
                </p>
              <% true -> %>
                <p>This release does not name an introductory Climb.</p>
            <% end %>
          </section>

          <section id="test-skill" class="doc-section">
            <h2>Test your Skill</h2>
            <p>
              Techtree makes practice tasks from what your Skill teaches, then your agent works
              them without the Skill and with it. Every step that sends anything to a model prints
              a review first and waits for your yes. Each command prints the next one.
            </p>
            <h3>1. Make the tasks</h3>
            <.command_block
              id="copy-docs-skill-tasks"
              lines={[
                {:command, ["techtree", "forge", "inspect-skill", "path/to/your-skill"]},
                {:command,
                 [
                   "techtree",
                   "forge",
                   "plan",
                   "SOURCE_ID",
                   "--provider",
                   "PROVIDER",
                   "--model",
                   "MODEL"
                 ]},
                {:comment, "Review, correct, build and accept, one printed step at a time."}
              ]}
              label="Make tasks from a Skill"
            />
            <p>
              Accepting the tasks that qualified gives you a collection. Some of its tasks are
              held out from anyone improving the Skill.
            </p>
            <h3>2. Run them both ways, then compare</h3>
            <.command_block
              id="copy-docs-skill-compare"
              lines={[
                {:command,
                 [
                   "techtree",
                   "forge",
                   "run",
                   "--arm",
                   "baseline",
                   "--collection",
                   "COLLECTION_ID",
                   "--provider",
                   "PROVIDER",
                   "--model",
                   "MODEL"
                 ]},
                {:command,
                 [
                   "techtree",
                   "forge",
                   "run",
                   "--arm",
                   "candidate",
                   "--collection",
                   "COLLECTION_ID",
                   "--provider",
                   "PROVIDER",
                   "--model",
                   "MODEL",
                   "--skill",
                   "path/to/your-skill"
                 ]},
                {:command, ["techtree", "forge", "compare", "BASELINE_RUN_ID", "CANDIDATE_RUN_ID"]}
              ]}
              label="Compare without and with the Skill"
            />
            <p>
              Both runs use the same provider and model. The comparison calls no model: it pairs
              every task across the two runs and says whether the Skill improved, regressed, was
              mixed or made no difference, overall and on the held-out tasks alone. It writes a
              report you can open in a browser. The
              <.link navigate={~p"/examples/tdd"}>tdd example</.link>
              shows a finished one.
            </p>
            <h3>3. Revise once, if you want to</h3>
            <p>
              <code>techtree uplift context COMPARISON_ID</code>
              gives what a revision may learn from, never the held-out tasks. Write the revised
              Skill into a new folder, then run
              <code>
                techtree uplift prepare --from-run COMPARISON_ID --candidate-skill path/to/revised-skill
              </code>
              and the <code>techtree uplift start</code>
              command it prints. The revision is judged on the held-out tasks alone.
            </p>
            <h3>Fix a task, or check where things stand</h3>
            <p>
              If a built task is wrong, fix a copy of it by hand and record that with <code>techtree forge correct-task CONSTRUCTION_ID TASK_NAME DIR</code>.
              <code>techtree forge status ID</code>
              shows any build, plan, run or comparison.
              <code>techtree forge export COLLECTION_ID --to FOLDER</code>
              writes a copy of the tasks for someone else to rerun.
            </p>
          </section>

          <section id="two-versions" class="doc-section">
            <h2>Compare two versions of a Skill</h2>
            <p>
              To decide whether a change is worth keeping, give the baseline run the earlier
              version instead of no Skill. Keep the earlier version in its own folder.
            </p>
            <.command_block
              id="copy-docs-two-versions"
              argv={[
                "techtree",
                "forge",
                "run",
                "--arm",
                "baseline",
                "--collection",
                "COLLECTION_ID",
                "--provider",
                "PROVIDER",
                "--model",
                "MODEL",
                "--skill",
                "path/to/earlier-skill"
              ]}
              label="Baseline with the earlier version"
            />
            <p>
              Then run the candidate with the new version and compare the two runs, exactly as
              above.
            </p>
          </section>

          <section id="first-climb" class="doc-section">
            <h2>Take a quick look with the Hello World Climb</h2>
            <p>
              The Hello World Climb is a small, fixed comparison that ships with the release, run
              with a starter Skill. It shows how a run is approved and what a Result looks like.
              Its toy tasks say nothing about your own Skill. Preparation prints the exact one-time
              start command and the most the run may spend before anything runs.
            </p>
            <.command_block
              :if={@release && @release.introductory_reference}
              id="copy-docs-prepare"
              lines={[
                {:command, ["techtree", "skill", "starter"]},
                {:command,
                 [
                   "techtree",
                   "climb",
                   "prepare",
                   @release.introductory_reference,
                   "--skill",
                   "path/to/skill"
                 ]}
              ]}
              label="Prepare the Hello World Climb"
            />
            <p>
              Approve and run only the exact <code>techtree climb start</code> command printed by
              preparation. Closing the terminal does not stop a started Run.
            </p>
          </section>

          <section id="hermes" class="doc-section">
            <h2>
              Use <a href="https://github.com/NousResearch/hermes-agent">Hermes</a>
            </h2>
            <p>
              Hermes can run every step itself, like any coding agent. Give it the same
              instruction:
            </p>
            <.prompt_block id="copy-docs-hermes" label="Give this to Hermes" text={@instruction} />
            <p>
              Hermes may prepare commands and explain output. Techtree still stops before every
              model call and waits for your own yes.
            </p>
            <p :if={@plugin_commands}>
              The Techtree plugin for Hermes adds commands for the Hello World Climb and for
              publishing its Results:
            </p>
            <.command_block
              :if={@plugin_commands}
              id="copy-docs-hermes-plugin"
              lines={@plugin_commands}
              label="Hermes plugin"
            />
          </section>

          <section id="verify" class="doc-section">
            <h2>Verify a Result locally</h2>
            <p>
              Verification reads a Result bundle, recomputes its checks, and makes no model call.
              Give it the run’s ID, the bundle’s folder, or a bundle downloaded from a published
              Result’s page.
            </p>
            <.command_block
              id="copy-docs-verify"
              argv={["techtree", "proof", "verify", "path/to/result-bundle"]}
              label="Verify locally"
            />
            <p><.link navigate={~p"/proofs"}>Read exactly what verification establishes.</.link></p>
          </section>

          <section id="publish" class="doc-section">
            <h2>Publish a Result</h2>
            <p>
              Only Climb runs can be published today. A Skill comparison stays on your computer;
              <code>techtree forge export</code>
              writes a copy of its tasks to share.
            </p>
            <p>
              Publishing is a separate action performed after a Run finishes. The CLI shows the
              publication terms and asks before it sends the Result bundle.
            </p>
            <.command_block
              id="copy-docs-publish"
              argv={["techtree", "publish", "RUN_ID"]}
              label="Publish one finished Run"
            />
            <p>
              The server returns a signed publication receipt and repeated publication of the same
              bundle is idempotent. Published comparisons appear in <.link navigate={~p"/results"}>Results</.link>.
            </p>
            <.command_block
              id="copy-docs-withdraw"
              argv={["techtree", "withdraw", "BUNDLE_DIGEST"]}
              label="Withdraw a published Result"
            />
            <p>
              Withdrawing marks the entry withdrawn and stops offering its bundle. The page keeps
              its address, and copies anybody already holds are still theirs to check.
            </p>
          </section>

          <section id="integration" class="doc-section">
            <h2>Use the machine interface</h2>
            <p>
              Pass <code>--json</code> to CLI commands for one machine-readable envelope on stdout.
              Machine mode does not prompt; operational messages go to stderr.
            </p>
            <.definition_list>
              <:fact term="Release bootstrap"><code>GET /api/v1/bootstrap</code></:fact>
              <:fact term="Published Climb catalog"><code>GET /api/v1/catalog</code></:fact>
              <:fact term="One Climb"><code>GET /api/v1/climbs/:slug</code></:fact>
              <:fact term="Published Results"><code>GET /api/v1/publications</code></:fact>
              <:fact term="One published Result"><code>GET /api/v1/publications/:digest</code></:fact>
              <:fact term="Publication key"><code>GET /api/v1/publication-keys/:key_id</code></:fact>
            </.definition_list>
            <p>
              Protocol payloads retain their schema field names even where the public site uses
              simpler words.
            </p>
          </section>

          <section id="browser-tools" class="doc-section">
            <h2>Let a browser's agent read Techtree</h2>
            <div class="docs-prose">{raw(PublicDocuments.docs_section("Browser tools"))}</div>
          </section>

          <section
            :for={
              {id, heading} <- [
                {"errors", "Errors"},
                {"rate-limits", "Rate limits"},
                {"versioning", "Versioning and deprecation"}
              ]
            }
            id={id}
            class="doc-section"
          >
            <h2>{heading}</h2>
            <div class="docs-prose">{raw(PublicDocuments.docs_section(heading))}</div>
          </section>

          <section id="data-boundary" class="doc-section">
            <h2>Know what leaves the machine</h2>
            <p>
              Local Runs, Episodes, and Traces stay local. Model calls go to the provider you
              chose, or the one the Climb names. Techtree receives a Result bundle only when you
              explicitly publish it.
            </p>
            <p>No Techtree account or browser upload is required.</p>
          </section>

          <section id="troubleshooting" class="doc-section">
            <h2>Troubleshoot from the boundary inward</h2>
            <ol class="docs-numbered-list">
              <li>Run Doctor for the exact Climb reference.</li>
              <li>Read the next action and any missing prerequisite it reports.</li>
              <li>Use <code>techtree run status RUN_ID</code> for a started Run.</li>
              <li>Use <code>techtree run logs RUN_ID</code> for execution details.</li>
              <li>
                Use <code>techtree forge status ID</code> for a Skill test's build, plan, run or
                comparison.
              </li>
              <li>Re-run local verification before attempting publication again.</li>
            </ol>
            <p>
              Source and issue tracking live at <a href="https://github.com/regents-ai/techtree">github.com/regents-ai/techtree</a>.
            </p>
          </section>

          <TechtreeWeb.ResearchContent.sections />
        </article>
      </div>
    </Layouts.page>
    """
  end

  defp plugin_commands(%{
         installable?: true,
         plugin_install_argv: [_ | _] = install_argv,
         plugin_doctor_argv: [_ | _] = doctor_argv
       }) do
    [
      {:command, install_argv},
      {:command, doctor_argv},
      {:comment, "In a fresh Hermes session, enter:"},
      {:command, ["/techtree", "setup"]}
    ]
  end

  defp plugin_commands(_release), do: nil

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
