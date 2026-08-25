defmodule TechtreeWeb.HomeLive do
  @moduledoc """
  Techtree in one sentence, one installer, and one honest evidence graph.
  """

  use TechtreeWeb, :live_view

  alias Techtree.Catalog.Query
  alias TechtreeWeb.ClimbCopy
  alias TechtreeWeb.EvidenceComponents
  alias TechtreeWeb.EvidenceGraph
  alias TechtreeWeb.ReleaseInfo

  @impl true
  def mount(_params, _session, socket) do
    campaign = Query.list_climbs() |> List.first()

    {:ok,
     assign(socket,
       page_title: "Improve a Skill. Prove it worked.",
       campaign: campaign,
       campaign_copy: campaign && ClimbCopy.for_reference(campaign.reference),
       graph: EvidenceGraph.from_climb(campaign),
       release: ReleaseInfo.current()
     )}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page wide flush>
      <section class="hero" aria-labelledby="hero-title">
        <div class="hero__copy">
          <p class="eyebrow">Controlled improvement, on your machine</p>
          <h1 id="hero-title">Improve a Skill.<br />Prove it worked.</h1>
          <p class="hero__lede">
            Run a controlled baseline and candidate on your machine. Techtree keeps the
            taskset, model, harness, tools, and budget fixed, then signs the result so
            another participant can verify or reproduce it.
          </p>

          <div class="hero__actions">
            <a class="button button--primary" href={~p"/docs#install"}>Install Techtree</a>
            <a class="text-link" href={~p"/proofs"}>
              View a verified run <span aria-hidden="true">→</span>
            </a>
          </div>

          <.canonical_installer release={@release} />
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
          <p class="eyebrow">Active catalog · {@campaign.status}</p>
          <h2 id="featured-title">
            {(@campaign_copy && @campaign_copy.campaign_title) || @campaign.title}
          </h2>
          <p>{@campaign.summary}</p>
        </div>
        <dl class="featured__facts">
          <div>
            <dt>Tasks</dt>
            <dd>{@campaign.projection["task_count"]}</dd>
          </div>
          <div>
            <dt>Harness</dt>
            <dd>
              {@campaign.projection["subject_harness"]}
              {@campaign.projection["subject_harness_version"]}
            </dd>
          </div>
          <div>
            <dt>Evidence</dt>
            <dd>{validation_summary(@campaign.projection["task_validation"])}</dd>
          </div>
        </dl>
        <a class="text-link" href={~p"/campaigns/#{@campaign.projection["slug"]}"}>
          Inspect the campaign <span aria-hidden="true">→</span>
        </a>
      </section>

      <section class="home-section trust" aria-labelledby="trust-title">
        <div class="section-heading">
          <p class="eyebrow">Trust boundary</p>
          <h2 id="trust-title">Your work stays local.</h2>
        </div>
        <div class="trust__grid">
          <p>
            Techtree does not upload your recordings, result bundle, or submitted Skill.
            The agent still makes calls to the model provider you selected, under that
            provider's policies.
          </p>
          <p>
            A signed local proof establishes internal consistency and authorship. It
            becomes an independent reproduction only when another participant runs and
            attests to it.
          </p>
        </div>
        <p class="trust__links">
          <a href={~p"/docs#trust"}>Read the trust model</a>
          <span aria-hidden="true">·</span>
          <a href={~p"/protocol"}>Inspect the protocol</a>
        </p>
      </section>
    </Layouts.page>
    """
  end

  attr :release, :map, default: nil

  defp canonical_installer(assigns) do
    ~H"""
    <details class="canonical-installer">
      <summary>Install with CLI</summary>
      <div class="canonical-installer__body">
        <%= cond do %>
          <% is_nil(@release) -> %>
            <p class="release-state">No install release is active on this channel.</p>
          <% not @release.installable? -> %>
            <p class="release-state">
              This channel has placeholder coordinates. No install command is published.
            </p>
          <% true -> %>
            <.command_block
              id="copy-home-install"
              argv={@release.install_argv}
              label="Canonical v0.1 installer"
            />
            <p class="compatibility">{ReleaseInfo.compatibility(@release)}</p>
            <p class="release-coordinate">
              <span>{ReleaseInfo.label(@release)}</span>
              <a href={~p"/docs#release-coordinate"}>Release details</a>
            </p>
        <% end %>
      </div>
    </details>
    """
  end

  defp validation_summary(%{"valid" => total, "total" => total}),
    do: "#{total} tasks validated"

  defp validation_summary(%{"valid" => valid, "total" => total}),
    do: "#{valid} of #{total} tasks valid"

  defp validation_summary(_validation), do: "Not published"
end
