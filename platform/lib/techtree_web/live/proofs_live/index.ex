defmodule TechtreeWeb.ProofsLive.Index do
  @moduledoc """
  Public proofs deliberately released by participants.

  v0.1 has no publication intake and no account surface. Until a curated proof
  is added to the release catalog, this index stays empty instead of presenting
  private certification evidence as a participant result.
  """

  use TechtreeWeb, :live_view

  @impl true
  def mount(_params, _session, socket) do
    {:ok, assign(socket, page_title: "Public proofs")}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page wide>
      <header class="page-heading">
        <p class="eyebrow">Content-addressed results</p>
        <h1>Public proofs</h1>
        <p class="lede">
          A public proof should let you inspect the comparison before you trust the claim.
        </p>
      </header>

      <section class="empty-proof" aria-labelledby="empty-proof-title">
        <div class="empty-proof__mark" aria-hidden="true">
          <span></span><span></span><span></span>
        </div>
        <div>
          <h2 id="empty-proof-title">No proof is curated for public release yet.</h2>
          <p>
            Local proofs never upload automatically. The v0.1 catalog currently contains a
            real campaign and its publisher validation, but no participant proof with
            publication authorization.
          </p>
          <p>
            When one is released, its digest page will show the campaign, both branches,
            changed Skill, scores and uncertainty, task wins and losses, model and harness,
            environment, budget, evidence completeness, signature, reproductions, bundle,
            and offline verification command.
          </p>
          <p class="proof-actions">
            <a class="button" href={~p"/campaigns"}>Inspect campaigns</a>
            <a class="text-link" href={~p"/proofs/local"}>How local proof works →</a>
          </p>
        </div>
      </section>

      <section class="offline-verify">
        <div>
          <p class="eyebrow">Already have a bundle?</p>
          <h2>Verify it offline.</h2>
        </div>
        <.command_block
          id="copy-proof-index-verify"
          argv={["techtree", "proof", "verify", "path/to/result-bundle"]}
        />
      </section>
    </Layouts.page>
    """
  end
end
