defmodule TechtreeWeb.HomeLive do
  @moduledoc """
  What Techtree Climb is, in the fewest words that are still true.

  There is nothing on this page that changes: no counters, no activity, no
  claims about how many people have run anything. A reader arriving here should
  be able to tell within a paragraph whether this is for them.
  """

  use TechtreeWeb, :live_view

  @impl true
  def mount(_params, _session, socket) do
    {:ok, assign(socket, page_title: "Controlled trials for agent skills")}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page>
      <h1>Techtree Climb</h1>
      <p class="lede">Controlled trials for agent skills and harnesses.</p>

      <section class="section">
        <p>
          A Climb is an invitation to test one change. The same tasks are run twice
          under the same conditions: once as the agent is, and once with your change
          in place. Everything else is held fixed and recorded, so that the
          difference in score has only one thing left to be caused by.
        </p>

        <ul class="questions section">
          <li>What changed?</li>
          <li>What stayed fixed?</li>
          <li>Did the score move?</li>
          <li>Can the result be checked on the machine that produced it?</li>
        </ul>
      </section>

      <section class="section">
        <div class="actions">
          <a class="action action--primary" href={~p"/start"}>Start on your machine</a>
          <a class="action" href={~p"/climbs"}>Browse Climbs</a>
          <a class="action" href={~p"/protocol"}>Read the protocol</a>
        </div>
      </section>

      <section class="section">
        <h2>Where the work happens</h2>
        <p>
          Trials run on your own machine, in a clean container, against a published
          set of tasks. Your work and your recordings stay there: this site does not
          run trials, does not receive results, and has nothing to sign in to.
        </p>
        <p>
          A trial is not an offline exercise. The agent under test makes real model
          calls, and those go to the model provider you chose, under that provider's
          policies. What stays with you is everything else: the recordings, the
          result, and the work you submitted.
        </p>
        <p>
          What it publishes is the other half — the Climbs on offer and the exact
          documents that define them, each one served as the file it was generated
          from and checked against its fingerprint before it is handed over.
        </p>
      </section>

      <section class="section">
        <h2>What a result from your machine is worth</h2>
        <p>
          A result produced this way is signed by a key that lives on your machine.
          It can be checked, by anyone you give it to, without any server being
          involved: the documents it names are all fingerprinted, and the comparison
          it claims can be re-checked from them.
        </p>
        <p>
          It is not an independent reproduction, and this site does not describe it
          as one. Nobody else watched it happen. <a href={~p"/proofs/local"}>What a local result does and does not claim</a>.
        </p>
      </section>
    </Layouts.page>
    """
  end
end
