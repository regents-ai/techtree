defmodule TechtreeWeb.HomeLive do
  @moduledoc """
  What Techtree is, what it produces, and how to install it — in that order.

  Four regions and no more: the claim and the evidence behind it, the three
  steps that produce that evidence, the one campaign this release actually
  publishes, and where the work goes. Nothing on this page counts anything, and
  nothing on it moves: no activity, no totals, no claim about how many people
  have run anything.
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
  @preview_label "Local preview · v0.1 development release"

  @impl true
  def mount(_params, _session, socket) do
    campaign = Query.list_climbs() |> List.first()
    release = ReleaseInfo.current()

    {:ok,
     assign(socket,
       page_title: "Improve a Skill. Prove it worked.",
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
        <div class="hero__copy">
          <p class="eyebrow">{@preview_label}</p>
          <h1 id="hero-title">Improve a Skill.<br />Prove it worked.</h1>
          <p class="hero__lede">
            Run a controlled baseline and candidate on your machine. Techtree keeps the
            taskset, model, harness, tools, and budget fixed, then signs the result so
            another participant can verify or reproduce it.
          </p>

          <div class="hero__actions">
            <a class="button button--primary" href={~p"/docs#install"}>
              <span class="button__mark" aria-hidden="true"></span> Install Techtree
            </a>
            <a class="text-link" href={~p"/proofs"}>
              View a verified run <span aria-hidden="true">→</span>
            </a>
          </div>

          <p class="hero__caption">No Techtree account, and nothing to upload.</p>

          <.installer release={@release} />
        </div>

        <EvidenceComponents.graph
          :if={@graph != []}
          id="home-evidence-graph"
          nodes={@graph}
          compact
        />
      </section>

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
            <p>Sign the comparison, inspect its evidence, and let another machine reproduce it.</p>
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
            Techtree does not upload your recordings, your result bundle, or the work you
            submit. The agent under test makes real model calls, and those go to the model
            provider you selected, under that provider’s policies.
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

  # The one installation on this page, rendered from the published contract or
  # not rendered at all. On a narrow screen it is folded away behind its own
  # label; the words inside it are the same either way.
  attr :release, :map, default: nil

  defp installer(assigns) do
    ~H"""
    <details class="installer">
      <summary>Install with CLI</summary>
      <div class="installer__body">
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
              label="Quick install"
            />
            <p class="compatibility">{ReleaseInfo.compatibility(@release)}</p>
            <p class="release-coordinate">
              <span>{ReleaseInfo.label(@release)}</span>
              <a href={~p"/docs#release"}>Release details</a>
            </p>
        <% end %>
      </div>
    </details>
    """
  end
end
