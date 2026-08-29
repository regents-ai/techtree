defmodule TechtreeWeb.ClimbsLive.Show do
  @moduledoc """
  One Climb in full: what is compared, what is held fixed, what happens to your
  work, and where the documents behind all of it can be read.

  The page keeps two things apart that are easy to run together. The invitation
  says who may enter and what may be published. The trial says what is compared
  and how. They are different documents with different fingerprints, and a
  reader who conflates them will misread both.
  """

  use TechtreeWeb, :live_view

  alias Techtree.Catalog.Query
  alias TechtreeWeb.ClimbCopy

  @impl true
  def mount(%{"slug" => slug}, _session, socket) do
    case Query.get_climb_by_slug(slug) do
      {:ok, climb} ->
        {:ok,
         socket
         |> assign(page_title: climb.title)
         |> assign(climb: climb, facts: climb.projection)
         |> assign(copy: ClimbCopy.for_reference(climb.reference))}

      {:error, _error} ->
        raise TechtreeWeb.NotFoundError, "no Climb is published under that name"
    end
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page wide>
      <p class="small quiet"><a href={~p"/climbs"}>All Climbs</a></p>

      <div class="entry__head">
        <h1>{@climb.title}</h1>
        <.status_badge status={@climb.status} />
      </div>

      <p :if={@copy} class="plain quiet">{@copy.subtitle}</p>
      <p class="lede">{(@copy && @copy.scope) || @climb.summary}</p>

      <.warning_callout :if={@climb.status == "development"} title="This Climb is in development">
        <p>
          It exists to exercise the machinery end to end. A result from it says that
          the Test completed, and nothing about whether anything works better.
        </p>
      </.warning_callout>

      <section class="section">
        <h2>Two documents, two jobs</h2>
        <.comparison_boundary>
          <:side title="The invitation">
            <p>
              Who may enter, what may be submitted, what may be published, and how a
              result may be described.
            </p>
            <.digest value={fact(@facts, "climb_digest")} href={object_url(@facts, "climb_digest")} />
          </:side>
          <:side title="The Test">
            <p :if={@copy}><strong>{@copy.campaign_title}</strong></p>
            <p>
              What is compared, on which tasks, under which conditions, and how the
              score is decided. This is the part that has to stay fixed.
            </p>
            <.digest
              value={fact(@facts, "campaign_spec_digest")}
              href={object_url(@facts, "campaign_spec_digest")}
            />
          </:side>
        </.comparison_boundary>
      </section>

      <section class="section">
        <h2>What is measured</h2>
        <.definition_list>
          <:fact term="The question">{purpose_words(fact(@facts, "purpose"))}</:fact>
          <:fact term="What may differ">
            {mutation_words(get_in(@facts, ["mutation_contract", "kind"]))}
          </:fact>
          <:fact term="Tasks">{fact(@facts, "task_count")}</:fact>
          <:fact term="Score">
            {plain(get_in(@facts, ["scoring", "primary_reward"]))}, averaged across tasks.
            The change counts only if the candidate scores above the baseline.
          </:fact>
          <%!-- The Campaign declares a per-episode timeout and this page used
          to quote it. Nothing enforces it in v0.1, so quoting it told a reader
          runs are time-bounded when they are not. Decision 0025 settles it for
          this release: the declared value stays in the document, and no public
          surface states it. Enforcement is a v0.2 candidate and gets the
          sentence back when it is true. --%>
          <:fact term="Test order">{schedule_words(get_in(@facts, ["execution", "order"]))}</:fact>
        </.definition_list>
      </section>

      <section class="section">
        <h2>What is held fixed</h2>
        <.definition_list>
          <:fact term="The agent under test">
            {fact(@facts, "subject_harness")} {fact(@facts, "subject_harness_version")}
          </:fact>
          <:fact term="The model">
            {get_in(@facts, ["subject_model", "provider"])}
            {get_in(@facts, ["subject_model", "model_id"])}
          </:fact>
          <:fact term="Where it runs">
            A {get_in(@facts, ["subject_runtime", "type"])} container with {get_in(@facts, [
              "subject_runtime",
              "cpu"
            ])} cores and {get_in(@facts, ["subject_runtime", "memory_gb"])} GB of memory, with {network_words(
              get_in(@facts, ["subject_runtime", "network_policy"])
            )}
          </:fact>
          <:fact term="Who checks the answers">
            {plain(fact(@facts, "evaluation_backend"))}. The tasks were validated before
            the Climb was published.
          </:fact>
        </.definition_list>
      </section>

      <section class="section">
        <h2>What this asks of you</h2>
        <.definition_list>
          <:fact :for={{term, sentence} <- data_policy_lines(fact(@facts, "data_policy"))} term={term}>
            {sentence}
          </:fact>
        </.definition_list>
        <p class="small quiet">
          These terms are the ones written in the rights document below, and the
          command line asks you to accept them by name before a Test starts.
        </p>
      </section>

      <section class="section">
        <h2>Run this Climb</h2>
        <p :if={@copy}>
          <strong>{@copy.starter_skill}</strong> — {@copy.starter_note}
        </p>
        <p>
          The installation and first-run walkthrough lives on <.link navigate={~p"/start"}>Start</.link>. This page remains the fixed Test contract.
        </p>
      </section>

      <details class="section integrity-details">
        <summary>Integrity details</summary>
        <.definition_list>
          <:fact term="Climb reference">{@climb.reference}</:fact>
          <:fact term="The invitation">
            <.protocol_badge name="ClimbManifest" />
            <.digest value={fact(@facts, "climb_digest")} href={object_url(@facts, "climb_digest")} />
          </:fact>
          <:fact term="The trial">
            <.protocol_badge name="CampaignSpec" />
            <.digest
              value={fact(@facts, "campaign_spec_digest")}
              href={object_url(@facts, "campaign_spec_digest")}
            />
          </:fact>
          <:fact term="The rights">
            <.protocol_badge name="DataPolicy" />
            <.digest
              value={fact(@facts, "data_policy_digest")}
              href={object_url(@facts, "data_policy_digest")}
            />
          </:fact>
          <:fact term="The task validation">
            <.protocol_badge name="TasksetValidationReceipt" />
            <.digest
              value={fact(@facts, "validation_receipt_digest")}
              href={object_url(@facts, "validation_receipt_digest")}
            />
          </:fact>
        </.definition_list>
        <p class="small quiet">
          Each link returns the document exactly as it was generated. The address is
          its fingerprint, and the file is checked against it before it is sent.
        </p>
      </details>
    </Layouts.page>
    """
  end

  defp fact(facts, key), do: Map.get(facts, key)

  defp object_url(facts, key) do
    case fact(facts, key) do
      digest when is_binary(digest) -> "/api/v1/objects/" <> digest
      _other -> nil
    end
  end

  defp plain(value) when is_binary(value), do: String.replace(value, "_", " ")
  defp plain(value), do: to_string(value)

  defp schedule_words("baseline_then_candidate"), do: "One after the other, on the same machine."
  defp schedule_words("parallel_variants"), do: "Side by side, started together on one machine."
  defp schedule_words(other), do: plain(other)

  defp network_words("restricted"), do: "the network restricted to what the tasks need."
  defp network_words("none"), do: "no network access."
  defp network_words(other), do: "network access: #{plain(other)}."
end
