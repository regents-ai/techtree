defmodule TechtreeWeb.ClimbsLive.Show do
  @moduledoc """
  The concise contract and setup instruction for one published Climb.
  """

  use TechtreeWeb, :live_view

  alias Techtree.Catalog.Query
  alias TechtreeWeb.CampaignFacts
  alias TechtreeWeb.ClimbCopy
  alias TechtreeWeb.Providers

  @impl true
  def mount(%{"slug" => slug}, _session, socket) do
    case Query.get_climb_by_slug(slug) do
      {:ok, climb} ->
        {:ok,
         assign(socket,
           page_title: climb.title,
           climb: climb,
           copy: ClimbCopy.for_reference(climb.reference),
           held_out_count: held_out_count(climb.projection["held_out_campaign_spec_digest"]),
           hub_package: hub_package(climb.projection["taskset_package"]),
           rubric: get_in(climb.projection, ["scoring", "rubric"])
         )}

      {:error, _error} ->
        raise TechtreeWeb.NotFoundError, "no Climb is published under that name"
    end
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page>
      <article class="climb-contract">
        <header>
          <p class="eyebrow">Climb</p>
          <h1>{@climb.title}</h1>
          <p :if={@copy} class="lede">{@copy.scope}</p>
          <p :if={@copy && @copy.result_note} class="lede">
            {@copy.result_note.text}
            <.link navigate={~p"/results/#{@copy.result_note.bundle_digest}"}>See that Result</.link>
          </p>
        </header>

        <dl class="climb-contract__facts">
          <div>
            <dt>Question</dt>
            <dd>{(@copy && @copy.question) || purpose_words(@climb.projection["purpose"])}</dd>
          </div>
          <div>
            <dt>Changed</dt>
            <dd>{mutation_words(get_in(@climb.projection, ["mutation_contract", "kind"]))}</dd>
          </div>
          <div>
            <dt>Tasks</dt>
            <dd>{@climb.projection["task_count"]}, fixed before either Run</dd>
          </div>
          <div :if={@held_out_count}>
            <dt>Held-out tasks</dt>
            <dd>
              {@held_out_count} more, kept apart. They are run once, on the winning Skill,
              and never decide the winner.
            </dd>
          </div>
          <div :if={@hub_package}>
            <dt>Environment</dt>
            <dd>
              <a href={hub_page(@hub_package["name"])} target="_blank" rel="noopener noreferrer">
                {@hub_package["name"]}
              </a>
              {@hub_package["version"]}, from Prime Intellect's Environments Hub. Every Run
              installs the exact copy this Climb names, even if a different copy is later
              published under the same version.
            </dd>
          </div>
          <div>
            <dt>Input</dt>
            <dd>{(@copy && @copy.input) || "Defined by the published task set."}</dd>
          </div>
          <div>
            <dt>Expected output</dt>
            <dd>{(@copy && @copy.output) || "Defined by the published scorer."}</dd>
          </div>
          <div>
            <dt>Scoring</dt>
            <dd>{(@copy && @copy.scoring) || rubric_words(@rubric["rewards"])}</dd>
          </div>
          <div>
            <dt>Held fixed</dt>
            <dd>{(@copy && @copy.held_fixed) || held_fixed_words(@climb)}</dd>
          </div>
        </dl>

        <div class="actions section">
          <.link class="rg-button rg-button--primary button--primary" navigate={~p"/start"}><span class="rg-button__label">Set up Techtree</span></.link>
          <a class="text-link" href={~p"/results"}>Browse Results from published Climbs</a>
        </div>
      </article>
    </Layouts.page>
    """
  end

  defp held_out_count(nil), do: nil

  defp held_out_count(digest) do
    digest
    |> CampaignFacts.campaign_by_digest!()
    |> CampaignFacts.for_campaign()
    |> get_in([:membership, "count"])
  end

  defp hub_package(%{"kind" => "hub"} = package), do: package
  defp hub_package(_embedded), do: nil

  # The Hub's page for an environment is named by its owner and name.
  defp hub_page(name) do
    [owner, environment] = String.split(name, "/")

    "https://app.primeintellect.ai/dashboard/environments/" <>
      URI.encode(owner, &URI.char_unreserved?/1) <>
      "/" <> URI.encode(environment, &URI.char_unreserved?/1)
  end

  defp rubric_words(rewards) do
    "Each task's score is the weighted total of the environment's own rewards, unchanged: " <>
      Enum.map_join(rewards, " + ", &"#{weight(&1["weight"])} × #{&1["name"]}") <>
      ". The Climb compares the mean of those scores over its tasks."
  end

  defp weight(value) when is_float(value) and value == trunc(value), do: trunc(value)
  defp weight(value), do: value

  defp held_fixed_words(climb) do
    "#{climb.projection["subject_harness"]} #{climb.projection["subject_harness_version"]}, " <>
      "#{Providers.name!(climb.projection["subject_model"]["provider"])} " <>
      climb.projection["subject_model"]["model_id"]
  end
end
