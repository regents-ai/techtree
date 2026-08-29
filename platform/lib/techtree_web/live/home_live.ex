defmodule TechtreeWeb.HomeLive do
  @moduledoc """
  Why Techtree exists, expressed through one concrete Skill comparison.
  """

  use TechtreeWeb, :live_view

  alias Techtree.Catalog.Query
  alias TechtreeWeb.ExampleResult

  # The milestone this preview is, said once. It is not an install coordinate:
  # the version, the fingerprint and the command all come from the published
  # release below, and none of them is written into this page.
  @preview_label "Techtree v0.1 · development release"

  @crown_studies [
    %{id: "1", label: "Graze"},
    %{id: "2", label: "Orange"},
    %{id: "3", label: "White"},
    %{id: "4", label: "Titanium"}
  ]
  @crown_actions %{crown_1: "1", crown_2: "2", crown_3: "3", crown_4: "4"}

  @impl true
  def mount(_params, _session, socket) do
    campaign = Query.list_climbs() |> List.first()
    crown_variant = Map.get(@crown_actions, socket.assigns.live_action, "1")
    crown_study? = Map.has_key?(@crown_actions, socket.assigns.live_action)

    {:ok,
     assign(socket,
       page_title: "Improve a Skill. Prove it worked.",
       campaign: campaign,
       example:
         ExampleResult.for_campaign(campaign && campaign.projection["campaign_spec_digest"]),
       preview_label: @preview_label,
       crown_studies: @crown_studies,
       crown_variant: crown_variant,
       crown_study?: crown_study?
     )}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page wide flush>
      <section
        class="hero"
        data-crown-variant={@crown_variant}
        data-crown-theme-controlled={if(@crown_study?, do: "false", else: "true")}
        aria-labelledby="hero-title"
      >
        <div
          id="hero-crown"
          class="hero__optics"
          phx-hook="Optics"
          phx-update="ignore"
          data-optics-kind="crown"
          data-optics-source={~p"/assets/js/crown_island.js"}
          data-optics-pointer="viewport"
          data-crown-variant={@crown_variant}
          data-crown-theme-controlled={if(@crown_study?, do: "false", else: "true")}
          aria-hidden="true"
        >
          <canvas
            id="hero-crown-canvas"
            class="hero__crown"
            data-optics-canvas
            data-crown-variant={@crown_variant}
          >
          </canvas>
        </div>

        <nav :if={@crown_study?} class="crown-studies" aria-label="Crown material studies">
          <span>Material study</span>
          <a
            :for={study <- @crown_studies}
            id={"crown-study-#{study.id}"}
            href={"/crown/#{study.id}"}
            data-crown-study={study.id}
            class={["crown-studies__link", study.id == @crown_variant && "is-active"]}
            aria-current={if(study.id == @crown_variant, do: "page")}
          >
            <b>{study.id}</b> {study.label}
          </a>
        </nav>

        <div class="hero__copy">
          <p class="eyebrow">{@preview_label}</p>
          <h1 id="hero-title" class="hero-title">
            <span class="hero-title__line">Improve a Skill.</span>
            <span class="hero-title__line">Prove it worked.</span>
          </h1>
          <p class="hero__mechanism">
            <span>Same pinned agent. Same fixed tasks. One changed Skill.</span>
            <span>Get a signed local receipt for the difference.</span>
          </p>

          <article :if={@example} class="hero-result" aria-label="One concrete Result">
            <div>
              <p class="hero-result__label">One concrete Result</p>
              <p class="hero-result__comparison">Instructional Skill <span>vs No Skill</span></p>
            </div>
            <p class="hero-result__uplift">
              <strong>+{example_uplift(@example)}%</strong>
              <span>{@example.wins} better · {@example.ties} same · {@example.losses} worse</span>
            </p>
            <a href={~p"/proofs"}>Inspect the proof <span aria-hidden="true">→</span></a>
          </article>

          <div class="hero__actions">
            <.link class="button button--primary" navigate={~p"/start"}>
              <span class="button__mark" aria-hidden="true"></span> Start your first Climb
            </.link>
            <a class="text-link" href={~p"/results"}>
              View published Results <span aria-hidden="true">→</span>
            </a>
          </div>
        </div>

        <a
          class="hero__more"
          href="#why-techtree"
          aria-label="Continue to why Techtree exists"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="m6 5 6 6 6-6" />
            <path d="m6 12 6 6 6-6" />
          </svg>
        </a>
      </section>

      <section id="why-techtree" class="home-section process" aria-labelledby="process-title">
        <div class="section-heading">
          <p class="eyebrow">Why Techtree exists</p>
          <h2 id="process-title">Make Skill improvements legible.</h2>
        </div>
        <p class="lede">
          Agents can change for many reasons. Techtree fixes the Test around one Skill change,
          then makes the resulting comparison easy to inspect and share.
        </p>
        <p class="trust__links">
          <a href={~p"/proofs"}>Understand the proof boundary</a>
          <span aria-hidden="true">·</span>
          <a :if={@campaign} href={~p"/climbs/#{@campaign.projection["slug"]}"}>
            Read the fixed Test contract
          </a>
        </p>
      </section>
    </Layouts.page>
    """
  end

  defp example_uplift(example) do
    example.candidate_total
    |> Kernel.-(example.baseline_total)
    |> Kernel./(example.tasks)
    |> Kernel.*(100)
    |> Float.round(1)
  end
end
