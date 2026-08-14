defmodule TechtreeWeb.LocalProofLive do
  @moduledoc """
  What a result produced on a participant's own machine does and does not claim.

  This page exists to prevent one specific misunderstanding: that a signed
  result is an independent one. It is not, this site never says it is, and
  there is nowhere here to send one.
  """

  use TechtreeWeb, :live_view

  @impl true
  def mount(_params, _session, socket) do
    {:ok, assign(socket, page_title: "Results from your machine")}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page>
      <h1>Results from your machine</h1>
      <p class="lede">
        What a locally produced result proves, what it does not, and how to check it.
      </p>

      <section class="section">
        <h2>What it is</h2>
        <p>
          When a trial finishes, your machine writes a bundle: the two runs, the
          documents they were run under, the scores the evaluation produced, and a
          summary of the difference. The bundle is signed with a key that was created
          on your machine and never leaves it.
        </p>
        <p>
          Everything inside is addressed by a fingerprint of its contents. Change one
          character of one file and the check fails.
        </p>
      </section>

      <section class="section">
        <h2>What can be checked, and by whom</h2>
        <.definition_list>
          <:fact term="The files are the files">
            Every document the result names is present and matches its fingerprint.
          </:fact>
          <:fact term="Only one thing differed">
            The two runs agree everywhere the Climb required them to agree, and differ
            only where it allowed.
          </:fact>
          <:fact term="The scores are the scores">
            The numbers in the summary are the ones the evaluation recorded, task by
            task.
          </:fact>
          <:fact term="The signature holds">
            The bundle was signed by the key that produced it and has not been edited
            since.
          </:fact>
        </.definition_list>
        <p>
          All four are checked without a network connection, by anyone you hand the
          bundle to:
        </p>
        <.command_block argv={["techtree", "proof", "verify", "path/to/result-bundle"]} />
      </section>

      <section class="section">
        <h2>What it does not claim</h2>
        <.warning_callout title="Nobody else watched this run" attention>
          <p>
            This site did not witness the trial, did not receive its recordings, and
            cannot vouch for the machine it ran on. A result that checks out is
            internally consistent and attested by the person who produced it. That is
            a real and useful thing, and it is not the same as an independent
            reproduction.
          </p>
        </.warning_callout>
        <p class="section">
          Nor did the trial run offline. The agent under test makes real model calls,
          and those go to the model provider you chose, under that provider's
          policies. If you take the guided revision of your Skill, that one request
          carries your Skill text and a sanitized summary of the run to the provider
          your own agent uses, which may be a different one. What never reaches this
          site is the recordings, the result bundle, and the work you submitted.
        </p>
        <p class="section">
          Nothing has been reproduced by a third party. No claim is made that the same
          result would appear on other hardware, with another model, or on another day.
          A result carries the grade the Climb offers, and that grade says which of
          these it is.
        </p>
      </section>

      <section class="section">
        <h2>Sending it somewhere</h2>
        <p>
          There is nowhere to upload a result on this site, by design. If you want to
          share one, share the bundle: it can be checked wherever it lands, and it
          contains no recordings unless you chose to include them.
        </p>
      </section>
    </Layouts.page>
    """
  end
end
