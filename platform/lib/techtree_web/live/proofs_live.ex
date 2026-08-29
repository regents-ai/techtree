defmodule TechtreeWeb.ProofsLive do
  @moduledoc """
  The exact boundary of Techtree's participant-attested verification.
  """

  use TechtreeWeb, :live_view

  alias Techtree.Network.Bundle

  @impl true
  def mount(_params, _session, socket) do
    {:ok, assign(socket, page_title: "What verification establishes", checks: Bundle.checks())}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page wide>
      <header class="page-heading">
        <p class="eyebrow">Participant-attested</p>
        <h1>What verification establishes</h1>
        <p class="lede">
          Techtree verifies the contents and signatures of a Result bundle. It does not claim
          to have witnessed or reproduced the Test.
        </p>
      </header>

      <section class="doc-section">
        <p class="eyebrow">A passing bundle</p>
        <h2>Everything inside agrees.</h2>
        <ul class="checks">
          <li :for={{_name, sentence} <- @checks}>
            <span class="checks__mark" aria-hidden="true">✓</span>
            <span>{sentence}</span>
          </li>
        </ul>
      </section>

      <section class="doc-section">
        <p class="eyebrow">The boundary</p>
        <h2>Verification is not observation.</h2>
        <p>
          A passing bundle is internally consistent and signed by the participant-controlled
          key it names. It does not prove the machine behaved honestly, that an independent
          party watched the Test, that the result generalizes, or that anyone reproduced it.
        </p>
      </section>

      <section class="offline-verify">
        <div>
          <p class="eyebrow">Check a copy</p>
          <h2>Verify a Result offline.</h2>
          <p class="small quiet">Verification makes no model request and needs no network.</p>
        </div>
        <.command_block
          id="copy-proof-verify"
          argv={["techtree", "proof", "verify", "path/to/result-bundle"]}
          label="Verify offline"
        />
      </section>

      <p class="small quiet section">
        <a href={~p"/results"}>Browse published Results</a>
        · <a href={~p"/docs#proofs"}>Operate the verifier</a>
      </p>
    </Layouts.page>
    """
  end
end
