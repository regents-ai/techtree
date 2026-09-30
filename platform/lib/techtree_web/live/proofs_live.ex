defmodule TechtreeWeb.ProofsLive do
  @moduledoc """
  How a Result is made, what checking one establishes and what it does not, and
  how to check one offline.

  Published Results live at `/results`; this page explains the check.
  """

  use TechtreeWeb, :live_view

  alias Techtree.Network.Bundle

  @impl true
  def mount(_params, _session, socket) do
    {:ok,
     assign(socket,
       page_title: "Verify a Result",
       checks: Bundle.checks(),
       check_count: Bundle.check_count()
     )}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page wide>
      <div class="verification-page">
        <header class="editorial-heading">
          <p class="eyebrow">Verify</p>
          <h1>Check a Result yourself</h1>
          <p class="lede">
            When someone says a Skill made their agent better, you shouldn’t have to take their
            word for it. Every Result on Techtree is a signed record you can download and check on
            your own computer, without trusting this site.
          </p>
          <a href="#offline-verifier" class="text-link">Check a Result now →</a>
        </header>

        <section id="how-made" class="section" aria-labelledby="how-made-title">
          <h2 id="how-made-title">How a Result is made</h2>
          <ol class="verify-check-grid verify-steps">
            <li class="verify-check rg-panel">
              <span class="verify-check__index">01</span>
              <h3>The agent works the same tasks twice</h3>
              <p>
                An agent run by Nous Research’s Hermes works a Climb’s fixed tasks once without
                the Skill and once with it. The model, the tools and the limits stay the same.
              </p>
              <a
                href="https://github.com/NousResearch/hermes-agent"
                target="_blank"
                rel="noopener noreferrer"
                class="text-link"
              >
                Hermes on GitHub ↗
              </a>
            </li>
            <li class="verify-check rg-panel">
              <span class="verify-check__index">02</span>
              <h3>Prime Intellect’s Verifiers scores every task</h3>
              <p>
                Prime Intellect’s Verifiers, an open-source library for testing AI agents, gives
                the agent each task and scores its answer by that task’s own rules.
              </p>
              <a
                href="https://github.com/PrimeIntellect-ai/verifiers"
                target="_blank"
                rel="noopener noreferrer"
                class="text-link"
              >
                Read Prime Intellect’s Verifiers ↗
              </a>
            </li>
            <li class="verify-check rg-panel">
              <span class="verify-check__index">03</span>
              <h3>The record is signed</h3>
              <p>
                The tasks, every score, the Skill and the settings go into one signed record: the
                Result. Changing any of it afterwards breaks the signature.
              </p>
              <a href={~p"/results"} class="text-link">See published Results →</a>
            </li>
          </ol>
        </section>

        <section
          id="local-results"
          class="verification-boundary section"
          aria-label="What a check tells you"
        >
          <div>
            <h2>What a check tells you</h2>
            <div class="verify-check-grid">
              <Regent.Structure.panel
                :for={
                  {index, title, description, href} <- [
                    {"01", "Nothing changed after signing",
                     "Every part of the Result still matches the signature made when the run finished.",
                     "/docs#proof-bundle"},
                    {"02", "Only the Skill changed",
                     "Both runs used the same tasks in the same order, the same model and the same settings. The Skill is the only difference.",
                     "/docs#method"},
                    {"03", "The verdict adds up",
                     "Better, worse or no different follows from the task scores, by the rule the Climb set before the run.",
                     "/docs#proof-bundle"},
                    {"04", "Nothing private is inside",
                     "A Result holds scores, not the agent’s conversations or anything from the computer it ran on.",
                     "/docs#data-boundary"}
                  ]
                }
                class="verify-check"
              >
                <span class="verify-check__index">{index}</span>
                <h3>{title}</h3>
                <p>{description}</p>
                <a href={href} class="text-link">How this is checked →</a>
              </Regent.Structure.panel>
            </div>
          </div>
          <Regent.Structure.panel class="boundary__side rg-panel__body rg-support-panel">
            <h2>What a check can’t tell you</h2>
            <ul class="verification-summary">
              <li>Techtree did not watch the run happen.</li>
              <li>
                The signature shows which key signed, not that the computer behind it was honest.
              </li>
              <li>A better score on these tasks doesn’t mean better at everything.</li>
              <li>One Result is one run. Only a separate rerun shows that it repeats.</li>
            </ul>
          </Regent.Structure.panel>
        </section>

        <section id="why-it-matters" class="section">
          <h2>Why it matters</h2>
          <p class="verification-why">
            Skills are easy to claim and hard to compare. A Result anyone can check turns “this
            Skill helps” into something you can test for yourself, and it stays checkable without
            this site: all you need is the Result and the free command below.
          </p>
        </section>

        <section id="offline-verifier" class="offline-verify">
          <div>
            <p class="eyebrow">Check it yourself</p>
            <h2>Check a Result on your computer.</h2>
            <p class="small quiet">
              Download the Result from its page, then run this command. It repeats every check on
              your own computer, runs no model and costs nothing.
            </p>
          </div>
          <.command_block
            id="copy-proof-verify"
            argv={["regents", "techtree", "proof", "verify", "path/to/result-bundle"]}
            label="Check a Result"
          />
        </section>

        <Regent.Primitives.disclosure
          class="integrity-details"
          id="verifier-checks"
          summary={"Every check, in order · #{@check_count} checks"}
        >
          <ol class="checks">
            <li :for={{_name, words} <- @checks}>{words}</li>
          </ol>
        </Regent.Primitives.disclosure>

        <p class="small quiet section">
          For the full method, read the <a href={~p"/docs#method"}>Docs</a>, copyable as
          Markdown to your agent.
        </p>

        <p class="small quiet section">
          <a href={~p"/results"}>Browse Results</a>
          · <a href={~p"/docs#verify"}>How to run the check</a>
        </p>
      </div>
    </Layouts.page>
    """
  end
end
