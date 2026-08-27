defmodule TechtreeWeb.HomeLive do
  @moduledoc """
  What Techtree is, what it produces, and how to install it — in that order.

  Five regions and no more: the claim and the evidence behind it, what this
  release is (decision 0035 — a proof of concept for a stack of three
  independent parts, two of them other people's work), the three steps that
  produce that evidence, the one campaign this release actually publishes, and
  where the work goes. Nothing on this page counts anything, and nothing on it
  moves: no activity, no totals, no claim about how many people have run
  anything.

  Under the headline is the one install panel, and it holds two ways in, in
  order. First the line a reader hands to their agent, because that is who sets
  this up; it is copied in one action and it names no release coordinate, so it
  is true for as long as this site is. Then, under a quiet divider, the path for
  somebody who would rather type it: the pinned command this release publishes,
  and the first thing to run once it has finished. Both of those come out of the
  served release record. Neither is written into this page, and when no release
  is being served the panel says so rather than printing a coordinate that
  installs nothing.

  Behind the headline sits one piece of decoration: a lattice of lit cubes, the
  mark extruded, drawn on the same ground as the page and carrying no text, no
  status and no number. Decision 0039 rules it in. It is not a second reading
  of anything — the evidence graph in front of it stays the page's only data
  layer — and a browser that cannot draw it simply does not.
  """

  use TechtreeWeb, :live_view

  alias Techtree.Catalog.Query
  alias TechtreeWeb.CampaignFacts
  alias TechtreeWeb.ClimbCopy
  alias TechtreeWeb.EvidenceComponents
  alias TechtreeWeb.EvidenceGraph
  alias TechtreeWeb.ReleaseInfo

  # The milestone this preview is, said once. It is not an install coordinate:
  # the version, the fingerprint and the command all come from the published
  # release below, and none of them is written into this page.
  @preview_label "Techtree v0.1 · development release"

  # The line a reader hands to their agent, decided by the founder and written
  # here once. It is an address on this site and the name of the introductory
  # Climb — neither of which belongs to any one release — so unlike a command it
  # is not read from the release record, and it stays true when the record moves.
  @agent_line "Go to techtree.sh/start and set up Techtree and run the Hello World Climb."

  @impl true
  def mount(_params, _session, socket) do
    campaign = Query.list_climbs() |> List.first()
    release = ReleaseInfo.current()

    {:ok,
     assign(socket,
       page_title: "Improve a Skill. Prove it worked.",
       agent_line: @agent_line,
       campaign: campaign,
       campaign_copy: campaign && ClimbCopy.for_reference(campaign.reference),
       campaign_facts: CampaignFacts.for_climb(campaign),
       graph: EvidenceGraph.from_climb(campaign, release),
       preview_label: @preview_label,
       release: release
     )}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page wide flush>
      <section class="hero" aria-labelledby="hero-title">
        <canvas
          id="hero-lattice"
          class="hero__lattice"
          phx-hook="HeroLattice"
          phx-update="ignore"
          aria-hidden="true"
        >
        </canvas>

        <div class="hero__copy">
          <p class="eyebrow">{@preview_label}</p>
          <h1 id="hero-title">Improve a Skill.<br />Prove it worked.</h1>
          <p class="hero__lede">
            Run a controlled baseline and candidate on your machine. Techtree keeps the
            taskset, model, harness, tools, and budget fixed, then signs the result so
            anyone holding a copy can check it offline, needing no account and nothing
            from us.
          </p>

          <.installer release={@release} agent_line={@agent_line} />

          <div class="hero__actions">
            <a class="button button--primary" href={~p"/docs#install"}>
              <span class="button__mark" aria-hidden="true"></span> Install Techtree
            </a>
            <a class="text-link" href={~p"/proofs"}>
              View a verified run <span aria-hidden="true">→</span>
            </a>
          </div>

          <p class="hero__caption">
            No Techtree account, and nothing uploaded unless you publish it.
          </p>
        </div>

        <EvidenceComponents.graph
          :if={@graph != []}
          id="home-evidence-graph"
          nodes={@graph}
          compact
        />
      </section>

      <.proof_of_concept
        class="home-section proof-of-concept"
        eyebrow="A proof of concept, not a product"
      />

      <section class="home-section process" aria-labelledby="process-title">
        <div class="section-heading">
          <p class="eyebrow">One controlled difference</p>
          <h2 id="process-title">Run. Improve. Prove.</h2>
        </div>
        <div class="process__steps">
          <article>
            <span>01</span>
            <h3>Run</h3>
            <p>Resolve a pinned campaign and record the baseline.</p>
          </article>
          <article>
            <span>02</span>
            <h3>Improve</h3>
            <p>Change one declared Skill under a fixed budget and validation rule.</p>
          </article>
          <article>
            <span>03</span>
            <h3>Prove</h3>
            <p>Sign the comparison, read the outcome of every task, and check the receipt offline.</p>
          </article>
        </div>
      </section>

      <section :if={@campaign} class="home-section featured" aria-labelledby="featured-title">
        <div>
          <p class="eyebrow">Published by this release</p>
          <h2 id="featured-title">
            {(@campaign_copy && @campaign_copy.campaign_title) || @campaign.title}
          </h2>
          <p>{@campaign.summary}</p>
        </div>
        <dl class="featured__facts">
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
        <a class="text-link" href={~p"/campaigns/#{@campaign.projection["slug"]}"}>
          Inspect the campaign <span aria-hidden="true">→</span>
        </a>
      </section>

      <section class="home-section trust" aria-labelledby="trust-title">
        <div class="section-heading">
          <p class="eyebrow">Where the work goes</p>
          <h2 id="trust-title">Your work stays local.</h2>
        </div>
        <div class="trust__grid">
          <p>
            Techtree uploads nothing on its own. Your recordings, your result bundle and
            the work you submit stay where they were made unless you publish a run
            yourself, and publishing sends the receipt rather than the recordings. The
            agent under test makes real model calls, and those go to the model provider
            you selected, under that provider’s policies.
          </p>
          <p>
            A result signed on your machine is internally consistent and attested by the
            participant who produced it. Nobody else watched the run, and this site never
            receives it.
          </p>
          <p class="trust__stack">
            The agent inside the experiment is Hermes, Nous Research’s open agent, at a
            pinned version. Every task is scored by Prime Intellect’s
            <.verifiers_term label="Verifiers" />, pinned
            just as exactly. Techtree fixes the conditions and signs the comparison.
          </p>
        </div>
        <p class="trust__links">
          <a href={~p"/docs#trust"}>What leaves my machine?</a>
          <span aria-hidden="true">·</span>
          <a href={~p"/proofs/local"}>What a local result claims</a>
        </p>
      </section>
    </Layouts.page>
    """
  end

  # The one installation on this page: two ways in, one under the other, with
  # the agent's line first because that is who does this.
  #
  # The half below the divider is the released one, and it is rendered from the
  # served release record or not rendered at all. A stand-in coordinate is
  # release state a reader may be told about; it is never handed over as
  # something to run.
  attr :release, :map, default: nil
  attr :agent_line, :string, required: true

  defp installer(assigns) do
    ~H"""
    <div class="installer">
      <.prompt_block id="copy-home-agent-line" label="Give this to your agent" text={@agent_line} />
      <p class="installer__caption">
        It reads the pinned installation guide, and asks you before it installs anything,
        runs anything, or spends anything.
      </p>

      <p class="installer__divider"><span>Or install it yourself</span></p>

      <div class="installer__manual">
        <%= cond do %>
          <% is_nil(@release) -> %>
            <p class="release-state">No release is published on this channel yet.</p>
          <% not @release.installable? -> %>
            <p class="release-state">
              This channel publishes stand-in coordinates, so there is no command to copy
              yet. The installation guide reads the same either way.
            </p>
          <% true -> %>
            <.command_block
              id="copy-home-install"
              argv={@release.install_argv}
              label="Install the command-line tool"
            />
            <.command_block
              :if={@release.introductory_reference}
              id="copy-home-doctor"
              argv={["techtree", "doctor", "--climb", @release.introductory_reference]}
              label="Then check this machine"
            />
            <p class="compatibility">{ReleaseInfo.compatibility(@release)}</p>
            <p class="release-coordinate">
              <span>{ReleaseInfo.label(@release)}</span>
              <a href={~p"/docs#release"}>Release details</a>
            </p>
        <% end %>
      </div>
    </div>
    """
  end
end
