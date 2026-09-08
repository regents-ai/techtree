defmodule TechtreeWeb.ProofsLive do
  @moduledoc """
  A compact reference for what bundle verification establishes and what it does not.

  Published proofs live at `/results`. This secondary page explains the verifier
  without competing with the evidence itself.
  """

  use TechtreeWeb, :live_view

  alias Techtree.Network.Bundle

  @impl true
  def mount(_params, _session, socket) do
    {:ok,
     assign(socket,
       page_title: "How verification works",
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
          <p class="eyebrow">Verifier reference</p>
          <h1>How verification works</h1>
          <p class="lede">
            Techtree checks a published Result bundle’s integrity, controlled comparison, score
            consistency, and publication policy. Verification makes the bundle internally
            checkable; it is not independent observation of the run.
          </p>
          <a href="#offline-verifier" class="text-link">Verify a bundle on your machine →</a>
        </header>

        <section
          id="local-results"
          class="verification-boundary section"
          aria-label="Verification boundary"
        >
          <div>
            <Regent.Structure.section_bar class="rg-support-band">
              <p class="rg-section-bar__label boundary__title">What Techtree verifies</p>
            </Regent.Structure.section_bar>
            <h2>Internally checkable evidence</h2>
            <div class="verify-check-grid">
              <Regent.Structure.panel
                :for={
                  {index, title, description, href} <- [
                    {"01", "Integrity", "Stored files match their digests and signatures.",
                     "/docs#proof-bundle"},
                    {"02", "Controlled comparison",
                     "Both branches use the same published Climb and ordered tasks, with only the permitted Skill changed.",
                     "/docs#method"},
                    {"03", "Score consistency", "The summary recomputes from task-level results.",
                     "/docs#proof-bundle"},
                    {"04", "Publication policy",
                     "The bundle contains no episodes, transcripts, or machine-local paths.",
                     "/docs#data-boundary"}
                  ]
                }
                class="verify-check"
              >
                <span class="verify-check__index">{index}</span>
                <h3>{title}</h3>
                <p>{description}</p>
                <a href={href} class="text-link">Read the method →</a>
              </Regent.Structure.panel>
            </div>
          </div>
          <Regent.Structure.panel class="boundary__side rg-panel__body rg-support-panel">
            <p class="boundary__title">What remains unproven</p>
            <h2>Verification is not observation</h2>
            <ul class="verification-summary">
              <li>The site did not witness the execution.</li>
              <li>The participant’s machine is not independently attested.</li>
              <li>The result does not establish generalization beyond the Climb.</li>
              <li>Nobody else reproduced it unless a separate reproduction says so.</li>
            </ul>
          </Regent.Structure.panel>
        </section>

        <Regent.Primitives.disclosure
          id="comparison"
          class="verification-method"
          summary="What stays fixed in a controlled comparison"
        >
          <p class="eyebrow">Method</p>
          <h2>The controlled comparison</h2>
          <p>Techtree runs the same fixed tasks twice.</p>
          <p>
            The model stays the same. The
            <a href="https://github.com/NousResearch/hermes-agent">Hermes</a>
            harness stays the same. The runtime, tools, scorer, task membership, sampling, and
            budget stay the same. Only the Skill may change.
          </p>
          <pre class="docs-code"><code>Same agent
    Same tasks
    Same evaluation

    Skill v1 → Skill v2</code></pre>
          <p>
            Prime Intellect’s <a href="https://github.com/PrimeIntellect-ai/verifiers">Verifiers</a>
            library runs and scores the tasks. Techtree checks that the comparison stayed
            controlled and packages the Result into a signed proof bundle.
          </p>
          <p>
            The Result may be an uplift, a tie, a regression, a failed Run, or an invalid
            comparison. Techtree does not turn every attempt into a success.
          </p>
        </Regent.Primitives.disclosure>

        <section id="offline-verifier" class="offline-verify">
          <div>
            <p class="eyebrow">Check it yourself</p>
            <h2>Verify a Result offline.</h2>
            <p class="small quiet">
              Anyone holding the participant’s bundle can run the same verifier on their own
              machine.
            </p>
          </div>
          <.command_block
            id="copy-proof-verify"
            argv={["techtree", "proof", "verify", "path/to/result-bundle"]}
            label="Verify offline"
          />
        </section>

        <Regent.Primitives.disclosure
          class="integrity-details"
          id="verifier-checks"
          summary={"Full verifier checklist · #{@check_count} checks"}
        >
          <ol class="checks">
            <li :for={{_name, words} <- @checks}>{words}</li>
          </ol>
        </Regent.Primitives.disclosure>

        <p class="small quiet section">
          For detailed information, read the <a href={~p"/docs#method"}>Docs</a>, copyable as
          Markdown to your agent.
        </p>

        <p class="small quiet section">
          <a href={~p"/results"}>Browse Results</a>
          · <a href={~p"/docs#verify"}>Operate the verifier</a>
        </p>
      </div>
    </Layouts.page>
    """
  end
end
