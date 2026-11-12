defmodule TechtreeWeb.ProofsLive do
  @moduledoc """
  How a Result is made, what checking one establishes and what it does not, and
  how to check one offline.

  Published Results live at `/results`; this page explains the check.
  """

  use TechtreeWeb, :live_view

  import TechtreeWeb.Components.Marketing, only: [field: 1, opening: 1]

  alias Techtree.Network.Bundle

  @impl true
  def mount(_params, _session, socket) do
    {:ok,
     assign(socket,
       page_title: "Offline check",
       checks: Bundle.checks(),
       check_count: Bundle.check_count()
     )}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page wide flush>
      <.opening
        eyebrow="Prove"
        title="Offline check"
        line="Every Result on Techtree is a signed record you can download and check on your own computer, without trusting this site."
        shape={3}
        icon="badge-check"
      >
        <:actions>
          <a href="#offline-verifier" class="rg-button rg-button--primary">Check offline</a>
        </:actions>
      </.opening>

      <section id="how-made" class="mk-section" aria-labelledby="how-made-title">
        <header class="mk-section__head">
          <h2 id="how-made-title">Method</h2>
          <p>
            When someone says a Skill made their agent better, you shouldn’t have to take their
            word for it.
          </p>
        </header>
        <ol
          id="how-made-steps"
          class="mk-cards"
          phx-hook="MarketingStagger"
          phx-update="ignore"
        >
          <li class="mk-card" data-stagger>
            <span class="mk-sequence__index">01</span>
            <h3>Two runs</h3>
            <p>
              An agent run by Nous Research’s Hermes works a Climb’s fixed tasks once without
              the Skill and once with it. The model, the tools and the limits stay the same.
            </p>
            <a
              href="https://github.com/NousResearch/hermes-agent"
              target="_blank"
              rel="noopener noreferrer"
              class="text-link mk-card__more"
            >
              Hermes on GitHub ↗
            </a>
          </li>
          <li class="mk-card" data-stagger>
            <span class="mk-sequence__index">02</span>
            <h3>Scoring</h3>
            <p>
              Prime Intellect’s Verifiers, an open-source library for testing AI agents, gives
              the agent each task and scores its answer by that task’s own rules.
            </p>
            <a
              href="https://github.com/PrimeIntellect-ai/verifiers"
              target="_blank"
              rel="noopener noreferrer"
              class="text-link mk-card__more"
            >
              Read Prime Intellect’s Verifiers ↗
            </a>
          </li>
          <li class="mk-card" data-stagger>
            <span class="mk-sequence__index">03</span>
            <h3>Signature</h3>
            <p>
              The tasks, every score, the Skill and the settings go into one signed record: the
              Result. Changing any of it afterwards breaks the signature.
            </p>
            <a href={~p"/results"} class="text-link mk-card__more">See published Results →</a>
          </li>
        </ol>
      </section>

      <section id="local-results" class="mk-section" aria-labelledby="local-results-title">
        <header class="mk-section__head">
          <h2 id="local-results-title">Checks</h2>
        </header>
        <div class="mk-split mk-split--wide">
          <ul class="mk-cards mk-cards--two">
            <li
              :for={
                {index, title, description, href} <- [
                  {"01", "Unchanged",
                   "Every part of the Result still matches the signature made when the run finished.",
                   "/docs/method"},
                  {"02", "Fair test",
                   "Both runs used the same tasks in the same order, the same model and the same settings. The Skill is the only difference.",
                   "/docs/method"},
                  {"03", "Verdict",
                   "Better, worse or no different follows from the task scores, by the rule the Climb set before the run.",
                   "/docs/method"},
                  {"04", "Nothing private",
                   "A Result holds scores, not the agent’s conversations or anything from the computer it ran on.",
                   "/docs/data"}
                ]
              }
              class="mk-card"
            >
              <span class="mk-sequence__index">{index}</span>
              <h3>{title}</h3>
              <p>{description}</p>
              <a href={href} class="text-link mk-card__more">How this is checked →</a>
            </li>
          </ul>
          <div class="mk-panel">
            <h3>Limits</h3>
            <ul class="mk-status">
              <li>Techtree did not watch the run happen.</li>
              <li>
                The signature shows which key signed, not that the computer behind it was honest.
              </li>
              <li>A better score on these tasks doesn’t mean better at everything.</li>
              <li>One Result is one run. Only a separate rerun shows that it repeats.</li>
            </ul>
          </div>
        </div>
      </section>

      <section id="why-it-matters" class="mk-section" aria-labelledby="why-it-matters-title">
        <header class="mk-section__head">
          <h2 id="why-it-matters-title">Purpose</h2>
          <p class="mk-statement__line">
            Skills are easy to claim and hard to compare. A Result anyone can check turns “this
            Skill helps” into something you can test for yourself, and it stays checkable without
            this site: all you need is the Result and the free command below.
          </p>
        </header>
      </section>

      <section
        id="offline-verifier"
        class="mk-band mk-dark"
        aria-labelledby="offline-verifier-title"
      >
        <.field id="offline-verifier-field" scene="mark" class="mk-band__field" />
        <div class="mk-band__copy">
          <h2 id="offline-verifier-title">Your computer</h2>
          <p class="mk-band__more">
            Download the Result from its page, then run this command. It repeats every check on
            your own computer, runs no model and costs nothing.
          </p>
          <.command_block
            id="copy-proof-verify"
            argv={["regents", "techtree", "proof", "verify", "path/to/result-bundle"]}
            label="Verify"
          />
        </div>
      </section>

      <section class="mk-section" aria-label="Every check">
        <Regent.Primitives.disclosure id="verifier-checks" summary={"#{@check_count} checks"}>
          <ol class="checks">
            <li :for={{_name, words} <- @checks}>{words}</li>
          </ol>
        </Regent.Primitives.disclosure>
        <p class="mk-section__note">
          For the full method, read the <a href={~p"/docs/method"}>Docs</a>, copyable as
          Markdown to your agent.
        </p>
        <p class="mk-links">
          <a href={~p"/results"} class="text-link">Browse Results</a>
          <a href={~p"/docs/verify"} class="text-link">How to run the check</a>
        </p>
      </section>
    </Layouts.page>
    """
  end
end
