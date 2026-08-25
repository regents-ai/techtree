defmodule TechtreeWeb.DocsLive do
  @moduledoc """
  The v0.1 quickstart and product reference, beginning with a working local run.
  """

  use TechtreeWeb, :live_view

  alias Techtree.Catalog.Query
  alias TechtreeWeb.ReleaseInfo

  @impl true
  def mount(_params, _session, socket) do
    {:ok,
     assign(socket,
       page_title: "Docs",
       release: ReleaseInfo.current(),
       campaign: Query.list_climbs() |> List.first()
     )}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page wide>
      <div class="docs-layout">
        <aside class="docs-nav" aria-label="Documentation sections">
          <p class="docs-nav__version">Version <strong>v0.1</strong></p>
          <nav>
            <.docs_group
              title="Start"
              links={[
                {"Quickstart", "#quickstart"},
                {"Install", "#install"},
                {"Hello World", "#hello-world"},
                {"Real campaign", "#real-campaign"}
              ]}
            />
            <.docs_group
              title="Concepts"
              links={[
                {"Campaigns", "#campaigns"},
                {"Baseline and candidate", "#comparison"},
                {"Run graph", "#run-graph"},
                {"Proofs", "#proofs"}
              ]}
            />
            <.docs_group
              title="Use Techtree"
              links={[
                {"CLI", "#cli"},
                {"Hermes", "#hermes"},
                {"Harnesses", "#harnesses"},
                {"Artifacts", "#artifacts"}
              ]}
            />
            <.docs_group
              title="Build"
              links={[
                {"Campaigns and adapters", "#build"},
                {"Integrations", "#integrations"}
              ]}
            />
            <.docs_group
              title="Trust"
              links={[
                {"What stays local", "#trust"},
                {"Proof limits", "#proof-limits"},
                {"Threat model", "#threat-model"}
              ]}
            />
            <.docs_group
              title="Reference"
              links={[
                {"Commands", "#command-reference"},
                {"Release", "#release-coordinate"},
                {"Protocol", "/protocol"},
                {"Troubleshooting", "#troubleshooting"}
              ]}
            />
          </nav>
        </aside>

        <article class="docs-content">
          <header class="docs-hero">
            <p class="eyebrow">Techtree v0.1</p>
            <h1>Get to a controlled first run.</h1>
            <p class="lede">
              Install the pinned CLI, check this machine, then prepare the Hello World
              campaign. Techtree prints the exact approved start command after preparation.
            </p>
          </header>

          <section id="quickstart" class="doc-section">
            <h2>Quickstart</h2>
            <%= if @release && @release.installable? do %>
              <ol class="quickstart">
                <li id="install">
                  <h3>Install the active release</h3>
                  <.command_block id="copy-docs-install" argv={@release.install_argv} />
                </li>
                <li>
                  <h3>Check this machine</h3>
                  <.command_block
                    id="copy-docs-doctor"
                    argv={["techtree", "doctor", "--climb", campaign_reference(@campaign)]}
                  />
                </li>
                <li id="hello-world">
                  <h3>Prepare the first comparison</h3>
                  <.command_block
                    id="copy-docs-prepare"
                    argv={[
                      "techtree",
                      "climb",
                      "prepare",
                      campaign_reference(@campaign),
                      "--skill",
                      "path/to/skill"
                    ]}
                  />
                  <p>
                    Review the declared tasks, budget, privacy terms, and changed Skill.
                    Preparation then prints the one-time <code>techtree climb start</code>
                    command; run that exact command to begin.
                  </p>
                </li>
              </ol>
              <p class="compatibility">{ReleaseInfo.compatibility(@release)}</p>
            <% else %>
              <aside id="install" class="callout">
                <p class="callout__title">Installation is not published on this channel</p>
                <p>
                  The site will show the canonical command here only after a concrete,
                  content-addressed v0.1 release becomes active. Placeholder coordinates are
                  never rendered as something to run.
                </p>
              </aside>
            <% end %>
          </section>

          <section id="trust" class="doc-section">
            <h2>What leaves my machine?</h2>
            <p>
              Techtree does not upload recordings, proof bundles, or your submitted Skill.
              The baseline and candidate make real calls to the model provider selected by
              the campaign. A guided revision sends the Skill text and a sanitized run
              summary to the provider used by your own agent.
            </p>
          </section>

          <section id="real-campaign" class="doc-section">
            <h2>Run a real campaign</h2>
            <%= if @campaign do %>
              <p>
                The active catalog currently publishes <a href={
                  ~p"/campaigns/#{@campaign.projection["slug"]}"
                }>{@campaign.title}</a>.
                It is marked <strong>{@campaign.status}</strong>; its page shows the exact
                model, harness, task count, budget, and validation receipt before you run it.
              </p>
            <% else %>
              <p>No campaign is active on this channel.</p>
            <% end %>
          </section>

          <section id="campaigns" class="doc-section">
            <h2>Campaigns</h2>
            <p>
              A campaign fixes the task membership, model, harness, tools, runtime, scoring,
              and budget for both branches. The public Climb is the invitation; the campaign
              is the comparison contract underneath it.
            </p>
          </section>

          <section id="comparison" class="doc-section">
            <h2>Baseline and candidate</h2>
            <p>
              Both branches use the same campaign coordinates. Only the declared component
              may change. In Hello World, the baseline has no Skill and the candidate adds
              exactly one Skill.
            </p>
          </section>

          <section id="run-graph" class="doc-section">
            <h2>Run graph, validation, and final test</h2>
            <p>
              The graph is an evidence index, not a progress illustration. A completed node
              must name a real artifact or receipt. Candidate search may explore privately;
              the final comparison is recorded separately under the fixed campaign.
            </p>
          </section>

          <section id="proofs" class="doc-section">
            <h2>Proofs and reproduction</h2>
            <p>
              A local proof binds the campaign, both branches, observed scores, and signer.
              It can be checked offline. It does not become independently reproduced until
              another participant runs the campaign and publishes a reproduction attestation.
            </p>
            <.command_block
              id="copy-docs-proof-verify"
              argv={["techtree", "proof", "verify", "path/to/result-bundle"]}
            />
          </section>

          <section id="cli" class="doc-section">
            <h2>Use Techtree</h2>
            <h3>From the CLI</h3>
            <p>
              Use <code>techtree doctor</code>
              before evaluation, <code>techtree climb</code>
              to prepare a comparison, <code>techtree run</code>
              to follow it, and <code>techtree proof verify</code>
              to check the finished bundle.
            </p>
            <h3 id="hermes">From Hermes</h3>
            <p>
              The pinned Hermes plugin provides the conversational path. Installation and
              every paid run still wait for explicit approval.
            </p>
            <h3>With Codex</h3>
            <p>
              Codex can operate the CLI from a local workspace. It is not a subject harness
              in the active v0.1 campaign, so the website does not label it as one.
            </p>
            <h3>Local dashboard</h3>
            <p>
              No separate local dashboard command exists in v0.1. Run status, logs, results,
              and proof verification are available through the CLI.
            </p>
          </section>

          <section id="harnesses" class="doc-section">
            <h2>Harness support</h2>
            <p>
              This list is derived from active campaign data. No broader adapter registry is
              published by this application today.
            </p>
            <dl class="support-matrix">
              <div :if={@campaign}>
                <dt>
                  {@campaign.projection["subject_harness"]}
                  {@campaign.projection["subject_harness_version"]}
                </dt>
                <dd>
                  <span class="state state--development">Development</span> Active campaign subject
                </dd>
              </div>
              <div>
                <dt>Codex subject adapter</dt>
                <dd>
                  <span class="state state--unavailable">Unavailable</span> Not in the active catalog
                </dd>
              </div>
            </dl>
          </section>

          <section id="artifacts" class="doc-section">
            <h2>Traces and artifacts</h2>
            <p>
              Run artifacts stay under the local Techtree home. Public catalog objects are
              served by content digest; local traces are not uploaded by this site.
            </p>
          </section>

          <section id="build" class="doc-section">
            <h2>Build</h2>
            <p>
              Campaign authors pin executable tasks, adapters, scorers, runtime, and budgets
              before publication. New harnesses and optimizers belong in the evaluation
              engine, not in this read-only website.
            </p>
            <p id="integrations">
              MCP and agent integrations should call the structured CLI surface and preserve
              its approval boundaries. The website accepts no runs or uploads.
            </p>
          </section>

          <section id="proof-limits" class="doc-section">
            <h2>What a proof establishes</h2>
            <p>
              Verification checks artifact digests, branch symmetry, task receipts, scores,
              and the participant signature. Evidence completeness is shown explicitly; a
              missing independent reproduction stays missing.
            </p>
          </section>

          <section id="threat-model" class="doc-section">
            <h2>Threat model</h2>
            <p>
              Techtree protects the comparison from accidental drift and makes tampering
              detectable. A participant-signed local proof does not prove the host was honest
              or that a third party watched execution.
            </p>
          </section>

          <section id="command-reference" class="doc-section">
            <h2>Command reference</h2>
            <p>
              Run <code>techtree --help</code> for the command list shipped by the installed
              release. v0.1 includes setup, doctor, climb, skill, run, engine, proof, release,
              and uplift commands.
            </p>
          </section>

          <section id="release-coordinate" class="doc-section">
            <h2>Release coordinates</h2>
            <%= if @release && @release.installable? do %>
              <dl class="facts facts--release">
                <dt class="facts__term">CLI version</dt>
                <dd class="facts__value">{@release.version}</dd>
                <dt class="facts__term">Bootstrap digest</dt>
                <dd class="facts__value digest">{@release.digest}</dd>
                <dt class="facts__term">Source revision</dt>
                <dd class="facts__value digest">{@release.source_revision}</dd>
              </dl>
            <% else %>
              <p>No concrete release coordinate is active on this channel.</p>
            <% end %>
          </section>

          <section id="troubleshooting" class="doc-section">
            <h2>Troubleshooting</h2>
            <p>
              Start with <code>techtree doctor --climb {campaign_reference(@campaign)}</code>.
              It checks the selected campaign's model credential, container runtime, engine,
              and local installation without starting a paid run.
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

  defp campaign_reference(nil), do: "hello-world-climb@1"
  defp campaign_reference(campaign), do: campaign.reference
end
