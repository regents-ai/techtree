defmodule TechtreeWeb.DocsLive do
  @moduledoc """
  The documentation: a working first run, then the ideas behind it.

  The order is the whole design. A reader arrives wanting to run something, so
  the first thing on the page is three commands and what they do, and the
  second is the answer to the question every one of those commands raises —
  what leaves this machine. Concepts come after both, because a concept a
  reader has already seen working is a different thing to read.

  Every command shown here is either read from the published release or is a
  command this build's own command-line tool actually offers. Nothing on this
  page is generated from a help output, and nothing describes a command that
  does not exist.
  """

  use TechtreeWeb, :live_view

  alias Techtree.Catalog.Query
  alias TechtreeWeb.CampaignFacts
  alias TechtreeWeb.ReleaseInfo

  @impl true
  def mount(_params, _session, socket) do
    campaign = Query.list_climbs() |> List.first()

    {:ok,
     assign(socket,
       page_title: "Docs",
       campaign: campaign,
       campaign_facts: CampaignFacts.for_climb(campaign),
       release: ReleaseInfo.current()
     )}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page wide>
      <div class="docs-layout">
        <aside class="docs-nav" aria-label="Documentation sections">
          <p class="docs-nav__version">Local preview</p>
          <nav>
            <.docs_group
              title="Start"
              links={[
                {"Quickstart", "#quickstart"},
                {"Install", "#install"},
                {"Run Hello World", "#hello-world"},
                {"What leaves my machine?", "#trust"}
              ]}
            />
            <.docs_group
              title="Concepts"
              links={[
                {"Campaigns", "#campaigns"},
                {"Subjects and harnesses", "#subjects"},
                {"Baseline and candidate", "#comparison"},
                {"Validation and final test", "#validation"},
                {"Run graph", "#run-graph"},
                {"Proofs and reproduction", "#proofs"}
              ]}
            />
            <.docs_group
              title="Use Techtree"
              links={[
                {"From the CLI", "#cli"},
                {"From Hermes", "#hermes"},
                {"Traces and artifacts", "#artifacts"}
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
                {"Commands", "#commands"},
                {"Exit codes", "#exit-codes"},
                {"Environment", "#environment"},
                {"Release coordinates", "#release"},
                {"Troubleshooting", "#troubleshooting"},
                {"Protocol documents", "/protocol"}
              ]}
            />
          </nav>
        </aside>

        <article class="docs-content">
          <header class="docs-hero">
            <p class="eyebrow">Local preview</p>
            <h1>Get to a controlled first run.</h1>
            <p class="lede">
              Install the pinned command-line tool, check this machine, then prepare the
              Hello World comparison. Preparation prints the one command that starts it,
              and nothing that spends model credits starts without you.
            </p>
          </header>

          <section id="quickstart" class="doc-section">
            <h2>Quickstart</h2>
            <%= if runnable?(@release, @campaign) do %>
              <ol class="quickstart">
                <li id="install">
                  <h3>Install the published release</h3>
                  <.command_block
                    id="copy-docs-install"
                    argv={@release.install_argv}
                    label="Quick install"
                  />
                  <p class="compatibility">{ReleaseInfo.compatibility(@release)}</p>
                </li>
                <li>
                  <h3>Check this machine</h3>
                  <.command_block
                    id="copy-docs-doctor"
                    argv={["techtree", "doctor", "--climb", @campaign.reference]}
                    label="Check this machine"
                  />
                  <p>
                    It checks the credential the campaign names, the container runtime, the
                    evaluation engine and the installation itself, without starting anything
                    that costs money.
                  </p>
                </li>
                <li id="hello-world">
                  <h3>Prepare the first comparison</h3>
                  <.command_block
                    id="copy-docs-prepare"
                    argv={[
                      "techtree",
                      "climb",
                      "prepare",
                      @campaign.reference,
                      "--skill",
                      "path/to/skill"
                    ]}
                  />
                  <p>
                    Review the declared tasks, the ceiling, the terms and the changed Skill.
                    Preparation then prints the one-time <code>techtree climb start</code>
                    command; running that exact command begins the two runs.
                  </p>
                </li>
              </ol>
            <% else %>
              <aside id="install" class="callout">
                <p class="callout__title">There is nothing to install from here yet</p>
                <p>
                  This channel publishes stand-in coordinates. The command appears here only
                  once a real, content-addressed release is the one being served — a stand-in
                  is never printed as something to run.
                </p>
              </aside>
            <% end %>
          </section>

          <section id="trust" class="doc-section">
            <h2>What leaves my machine?</h2>
            <p>
              Techtree does not upload your recordings, your result bundle, or the Skill you
              submit, and there is nowhere on this site to send them. The baseline and the
              candidate make real model calls, and those go to the model provider the
              campaign names, under that provider’s policies. A guided revision sends your
              Skill text and a sanitized summary of the run to the provider your own agent
              uses, which may be a different one.
            </p>
            <p>
              Running a comparison needs an account and a key with your model provider. It
              needs no Techtree account: this site has no sign-in, and nothing here knows
              who you are.
            </p>
          </section>

          <section id="campaigns" class="doc-section">
            <h2>Campaigns</h2>
            <p>
              A campaign fixes the comparison before either branch runs: which tasks, which
              model, which harness, which runtime, how the score is decided, and what a run
              may spend. It is a published document with a fingerprint, and both branches
              are read from that one document.
            </p>
            <p :if={@campaign}>
              This release publishes <a href={~p"/campaigns/#{@campaign.projection["slug"]}"}>{@campaign.title}</a>.
              Its page shows every coordinate above before you run anything.
            </p>
            <p :if={is_nil(@campaign)}>No campaign is published on this channel.</p>
          </section>

          <section id="subjects" class="doc-section">
            <h2>Subjects and harnesses</h2>
            <p>
              The subject is the agent under test: a harness at a pinned version, a model at
              a pinned coordinate, and a container image addressed by its own fingerprint.
              The campaign names all three, so the subject is not whatever happens to be
              installed on the machine that runs it.
            </p>
            <dl :if={@campaign} class="facts">
              <dt class="facts__term">Harness</dt>
              <dd class="facts__value">
                {@campaign.projection["subject_harness"]} {@campaign.projection[
                  "subject_harness_version"
                ]}
              </dd>
              <dt class="facts__term">Model</dt>
              <dd class="facts__value">{model_coordinate(@campaign.projection["subject_model"])}</dd>
            </dl>
          </section>

          <section id="comparison" class="doc-section">
            <h2>Baseline and candidate</h2>
            <p>
              Both branches run the same tasks under the same coordinates. Exactly one thing
              may differ, and the campaign says which: in Hello World the baseline mounts no
              Skill and the candidate mounts exactly one. Anything else that differed would
              make the comparison say nothing.
            </p>
          </section>

          <section id="validation" class="doc-section">
            <h2>Validation and final test</h2>
            <p>
              Before a campaign is published, the publisher checks every task in it and
              signs what was found. That receipt ships with the release and is addressed by
              its own fingerprint, so the tasks you run are the tasks that were checked.
            </p>
            <p :if={CampaignFacts.validation_words(@campaign_facts.validation)}>
              For the published campaign, that check reports <strong>{CampaignFacts.validation_words(@campaign_facts.validation)}</strong>.
            </p>
            <p>
              The final comparison is recorded separately from anything you tried while
              working on a Skill. Private exploration is yours; the recorded comparison is
              the one run under the fixed campaign.
            </p>
          </section>

          <section id="run-graph" class="doc-section">
            <h2>Run graph</h2>
            <p>
              The graph on this site is an index of evidence, not an illustration of
              progress. A node exists because a document exists, and opening one shows the
              document it came from. A branch that has been declared but not run says so.
            </p>
          </section>

          <section id="proofs" class="doc-section">
            <h2>Proofs and reproduction</h2>
            <p>
              When a comparison finishes, your machine writes a bundle: both runs, the
              documents they ran under, the scores recorded task by task, and a summary of
              the difference. It is signed with a key made on your machine that never leaves
              it, and anyone you hand the bundle to can check it without a network:
            </p>
            <.command_block
              id="copy-docs-proof-verify"
              argv={["techtree", "proof", "verify", "path/to/result-bundle"]}
              label="Verify offline"
            />
            <p>
              A checked bundle is internally consistent and attested by the participant who
              produced it. It becomes a reproduction only when someone else runs the same
              campaign and attests to what they got. This release publishes nothing and
              receives nothing, so no reproduction is offered here.
            </p>
          </section>

          <section id="cli" class="doc-section">
            <h2>From the CLI</h2>
            <p>
              The command-line tool is the whole product surface. Every command below is one
              this build ships; there is no command here that does not exist.
            </p>
            <.definition_list>
              <:fact term="techtree doctor">
                Check that this machine is ready to run a Climb. <code>--climb</code>
                checks the subject a particular Climb would run.
              </:fact>
              <:fact term="techtree setup">Prepare this machine to run a Climb.</:fact>
              <:fact term="techtree climb">
                Browse and enter Climbs: <code>list</code>, <code>show</code>, <code>prepare</code>, <code>start</code>.
              </:fact>
              <:fact term="techtree skill">
                Obtain the Skills a release names: <code>starter</code>.
              </:fact>
              <:fact term="techtree run">
                Follow and control your runs: <code>status</code>, <code>logs</code>, <code>cancel</code>, <code>result</code>.
              </:fact>
              <:fact term="techtree engine">
                Install and check the evaluation engine: <code>install</code>, <code>status</code>, <code>verify</code>.
              </:fact>
              <:fact term="techtree proof">
                Check local proofs: <code>verify</code>.
              </:fact>
              <:fact term="techtree release">
                Show and check the release this build belongs to: <code>info</code>, <code>verify</code>.
              </:fact>
              <:fact term="techtree uplift">
                <span class="state state--development">Experimental</span>
                Guided revision. <code>context</code>, <code>skill-source</code>, <code>prepare</code>, <code>start</code>. Your own agent proposes one
                revision and Techtree measures it the same way it measured the first
                attempt; a proposal may be unusable, or may run and change nothing.
              </:fact>
            </.definition_list>
            <p>
              Global options: <code>--home</code>
              for where local state is kept, <code>--json</code>
              for one machine-readable envelope instead of human output, <code>--no-color</code>, <code>--no-input</code>, <code>--debug</code>,
              and <code>--version</code>.
            </p>
          </section>

          <section id="hermes" class="doc-section">
            <h2>From Hermes</h2>
            <p>
              The pinned Hermes plugin gives the same commands a conversational front door:
              you ask, it shows you the exact command, and it waits for you before it
              installs anything or spends anything. The <a href={~p"/start"}>installation guide</a>
              carries the pinned plugin commands and what the install-time report will say.
            </p>
          </section>

          <section id="artifacts" class="doc-section">
            <h2>Traces and artifacts</h2>
            <p>
              Everything a run produces is written under the Techtree directory on your own
              machine: the recordings of each attempt, the per-task results, the logs, and
              the signed bundle. <code>techtree run result</code>
              prints the finished report, and <code>--json</code>
              gives the same thing in a form a program can read. None of it is sent
              anywhere.
            </p>
          </section>

          <section id="proof-limits" class="doc-section">
            <h2>What a proof establishes</h2>
            <p>
              Verification checks four things: that every document the result names is
              present and matches its fingerprint, that the two runs differed only where the
              campaign allowed, that the summary's numbers are the ones recorded task by
              task, and that the signature holds. It does not establish that the machine was
              honest or that anyone else watched.
            </p>
          </section>

          <section id="evidence" class="doc-section">
            <h2>Evidence completeness</h2>
            <p>
              A campaign declares which evidence a result must carry. What is missing stays
              visibly missing: a result never fills a gap with a default, and this site never
              draws a node for a document that does not exist.
            </p>
          </section>

          <section id="model-pinning" class="doc-section">
            <h2>Model pinning</h2>
            <p>
              The campaign pins the model the agent under test answers with, including its
              revision where the provider publishes one. You bring the account and the key;
              you do not choose the subject model, because a comparison whose model moved
              between the two runs measures the model, not the Skill.
            </p>
          </section>

          <section id="commands" class="doc-section">
            <h2>Command reference</h2>
            <p>
              The list above is the whole surface, and <code>techtree &lt;command&gt; --help</code>
              on your own installation is the authority for a given release. This page is
              written by hand against the commands this build ships, and says nothing about
              commands a later release might add.
            </p>
          </section>

          <section id="exit-codes" class="doc-section">
            <h2>Exit codes</h2>
            <p>
              A host agent branches on these without reading any output. They are
              append-only: a number never changes meaning.
            </p>
            <.definition_list>
              <:fact term="0">Finished as asked.</:fact>
              <:fact term="1">An error that has no more specific code.</:fact>
              <:fact term="2">The command was used incorrectly.</:fact>
              <:fact term="3">Something did not validate.</:fact>
              <:fact term="4">A prerequisite is missing on this machine.</:fact>
              <:fact term="5">What was asked for does not exist.</:fact>
              <:fact term="6">It conflicts with something already there.</:fact>
              <:fact term="7">A credential is missing or was refused.</:fact>
              <:fact term="8">A policy forbids it.</:fact>
              <:fact term="9">The evaluation engine failed.</:fact>
              <:fact term="10">The run itself failed.</:fact>
              <:fact term="11">Verification failed.</:fact>
              <:fact term="130">Cancelled.</:fact>
            </.definition_list>
          </section>

          <section id="environment" class="doc-section">
            <h2>Environment variables</h2>
            <.definition_list>
              <:fact term="TECHTREE_HOME">
                Where local state is kept. The <code>--home</code> option sets the same thing.
              </:fact>
              <:fact term="TECHTREE_OUTPUT_MODE">
                <code>human</code> or <code>json</code>, the same choice as <code>--json</code>.
              </:fact>
              <:fact term="TECHTREE_LOG_LEVEL">How much operational detail is written.</:fact>
              <:fact term="TECHTREE_ACTIVE_ENGINE_DIGEST">
                Which installed evaluation engine to use.
              </:fact>
            </.definition_list>
            <p>
              Your provider key is read from the variable the campaign names, at the moment
              the run needs it. Techtree never asks you for the value, never copies it into a
              run directory, and never writes it into any document.
              <code>techtree doctor --climb &lt;reference&gt;</code>
              names the variable it expects.
            </p>
          </section>

          <section id="release" class="doc-section">
            <h2>Release coordinates</h2>
            <%= if @release && @release.installable? do %>
              <.definition_list>
                <:fact term="Version">{@release.version}</:fact>
                <:fact term="Channel">{@release.channel}</:fact>
                <:fact term="Contract fingerprint">
                  <.digest value={@release.digest} />
                </:fact>
                <:fact term="Source revision">
                  <.digest value={@release.source_revision} />
                </:fact>
                <:fact :if={@release.repository_url} term="Pinned plugin">
                  <a href={@release.repository_url}>{@release.repository_url}</a>
                </:fact>
              </.definition_list>
            <% else %>
              <p>
                No real release coordinate is being served on this channel, so there is none
                to show.
              </p>
            <% end %>
          </section>

          <section id="troubleshooting" class="doc-section">
            <h2>Troubleshooting</h2>
            <p>
              Start with <code>techtree doctor</code>, and add <code>--climb &lt;reference&gt;</code>
              to check what one particular Climb needs. It reports the missing credential,
              the container runtime, the engine and the installation without starting a run
              that costs anything.
            </p>
            <p>
              If a run is already going, <code>techtree run status</code>
              says where it is, <code>techtree run logs</code>
              shows what it wrote, and <code>techtree run cancel</code>
              stops it. If the engine is the suspect, <code>techtree engine verify</code>
              confirms the installed one is intact.
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

  defp runnable?(%{installable?: true}, %{reference: reference}) when is_binary(reference),
    do: true

  defp runnable?(_release, _campaign), do: false

  defp model_coordinate(model) when is_map(model) do
    [model["provider"], model["model_id"], model["revision"]]
    |> Enum.reject(&(&1 in [nil, ""]))
    |> Enum.join(" · ")
  end

  defp model_coordinate(_model), do: "Not published"
end
