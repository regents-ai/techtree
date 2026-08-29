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
      <header class="page-heading">
        <p class="eyebrow">Verifier reference</p>
        <h1>How verification works</h1>
        <p class="lede">
          Techtree checks a published proof’s integrity, controlled comparison, score
          consistency, and publication policy. Verification makes the bundle internally
          checkable; it is not independent observation of the run.
        </p>
      </header>

      <section id="local-results" class="boundary section" aria-label="Verification boundary">
        <div class="boundary__side">
          <p class="boundary__title">What Techtree verifies</p>
          <h2>Internally checkable evidence</h2>
          <ul class="verification-summary">
            <li><strong>Integrity.</strong> Stored files match their digests and signatures.</li>
            <li>
              <strong>Controlled comparison.</strong> Both branches use the same published Climb
              and ordered tasks, with only the permitted Skill changed.
            </li>
            <li>
              <strong>Score consistency.</strong> The summary recomputes from task-level results.
            </li>
            <li>
              <strong>Publication policy.</strong> The bundle contains no episodes, transcripts,
              or machine-local paths.
            </li>
          </ul>
        </div>
        <div class="boundary__side">
          <p class="boundary__title">What remains unproven</p>
          <h2>Verification is not observation</h2>
          <ul class="verification-summary">
            <li>The site did not witness the execution.</li>
            <li>The participant’s machine is not independently attested.</li>
            <li>The result does not establish generalization beyond the Climb.</li>
            <li>Nobody else reproduced it unless a separate reproduction says so.</li>
          </ul>
        </div>
      </section>

      <section class="offline-verify">
        <div>
          <p class="eyebrow">Check it yourself</p>
          <h2>Verify a proof offline.</h2>
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

      <details class="integrity-details section" id="verifier-reference">
        <summary>Verifier reference: all {@check_count} checks</summary>
        <ol class="checks">
          <li :for={{_name, words} <- @checks}>{words}</li>
        </ol>
      </details>

      <p class="small quiet section">
        <a href={~p"/results"}>Browse Published Skill Capsules</a>
        · <a href={~p"/docs#proof-limits"}>Operate the verifier</a>
      </p>
    </Layouts.page>
    """
  end
end
