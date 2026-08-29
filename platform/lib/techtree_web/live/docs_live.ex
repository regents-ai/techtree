defmodule TechtreeWeb.DocsLive do
  @moduledoc """
  The concise operating and integration reference for Techtree.

  Commands containing release coordinates are rendered from the active release
  rather than copied into this page.
  """

  use TechtreeWeb, :live_view

  import TechtreeWeb.PageCopy, only: [page_copy: 1]

  alias TechtreeWeb.ReleaseInfo

  @impl true
  def mount(_params, _session, socket) do
    {:ok, assign(socket, page_title: "Docs", release: ReleaseInfo.current())}
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
              title="Get started"
              links={[
                {"Install and check", "#install"},
                {"Run the first Climb", "#first-climb"},
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
                {"Data boundary", "#data-boundary"},
                {"Troubleshooting", "#troubleshooting"}
              ]}
            />
            <.docs_group
              title="Method"
              links={[
                {"The question", "#method"},
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
              Install the released CLI, run your first A/B eval, verify a Result, and publish it
              to our public dashboard.
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

          <section id="first-climb" class="doc-section">
            <h2>Run the first Climb</h2>
            <p>
              Prepare the fixed comparison with the Skill you want to test. The preparation output
              shows the exact one-time start command and the model-spend ceiling before anything runs.
            </p>
            <.command_block
              :if={@release && @release.introductory_reference}
              id="copy-docs-prepare"
              argv={[
                "techtree",
                "climb",
                "prepare",
                @release.introductory_reference,
                "--skill",
                "path/to/skill"
              ]}
              label="Prepare the first Climb"
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
              The Hermes plugin is an operator interface over the same CLI. Give it this instruction:
            </p>
            <.prompt_block
              id="copy-docs-hermes"
              label="Give this to Hermes"
              text="Set up Techtree and run the Hello World Climb."
            />
            <p>
              Hermes may prepare commands and explain output. Techtree still stops before a paid
              model call and requires explicit approval.
            </p>
          </section>

          <section id="verify" class="doc-section">
            <h2>Verify a Result locally</h2>
            <p>
              Verification reads a Result bundle, recomputes its checks, and makes no model call.
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

          <section id="data-boundary" class="doc-section">
            <h2>Know what leaves the machine</h2>
            <p>
              Local Runs, Episodes, and Traces stay local. Model calls go to the provider selected
              by the Climb. Techtree receives a Result bundle only when you explicitly publish it.
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
