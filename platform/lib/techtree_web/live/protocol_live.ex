defmodule TechtreeWeb.ProtocolLive do
  @moduledoc """
  The map of documents the system is built from, for a technical reader.

  This is the one page written for someone who intends to read the documents
  themselves, so it names them the way the protocol names them — and still says
  what each one is for in a sentence. Where the active release ships an example,
  it is linked, and the link returns the exact bytes.
  """

  use TechtreeWeb, :live_view

  alias Techtree.Catalog.Query

  @documents [
    %{
      name: "DataPolicy",
      kind: :data_policy,
      schema: "techtree.data-policy.v1alpha1",
      role:
        "The rights that apply to everything one trial produces. Every later document copies its fingerprint, so a run cannot quietly change the terms it was started under."
    },
    %{
      name: "CampaignSpec",
      kind: :campaign,
      schema: "techtree.campaign.v1alpha1",
      role:
        "The trial itself: the tasks, the two things being compared, what may differ between them, how the score is decided, and what evidence is required."
    },
    %{
      name: "ClimbManifest",
      kind: :climb,
      schema: "techtree.climb.v1alpha1",
      role:
        "The public invitation to one trial: its name, its window, who may enter, and what may be published afterwards. It points at a CampaignSpec and holds nothing scientific of its own."
    },
    %{
      name: "TasksetValidationReceipt",
      kind: :taskset_validation,
      schema: "techtree.taskset-validation.v1alpha1",
      role:
        "The record that the tasks were checked before the trial was offered: which tasks, in which order, and what the checks found."
    },
    %{
      name: "ValidationEvidence",
      kind: :validation_evidence,
      schema: "techtree.validation-evidence.v1alpha1",
      role:
        "The task-by-task detail behind that record, kept separately because it is long and rarely needed."
    },
    %{
      name: "ExperimentManifest",
      kind: nil,
      schema: "techtree.experiment.v1alpha1",
      role:
        "What one particular run of a trial actually was, written before it starts: the exact documents, the exact two configurations, and the machine it will run on."
    },
    %{
      name: "EpisodeReceipt",
      kind: nil,
      schema: "techtree.episode-receipt.v1alpha1",
      role:
        "One task, run once: what was asked, what the agent did, what it scored, and which run it belonged to."
    },
    %{
      name: "UpliftReport",
      kind: nil,
      schema: "techtree.uplift-report.v1alpha1",
      role:
        "The difference between the two runs, with the checks that had to pass before the difference could be attributed to the change."
    },
    %{
      name: "LocalProofBundle",
      kind: nil,
      schema: "techtree.local-proof.v1alpha1",
      role:
        "Everything above, gathered and signed on the machine that produced it, so that it can be checked offline."
    }
  ]

  @impl true
  def mount(_params, _session, socket) do
    {:ok,
     socket
     |> assign(page_title: "Protocol")
     |> assign(documents: @documents)
     |> assign(shipped: shipped_objects())}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <Layouts.page wide>
      <h1>Protocol</h1>
      <p class="lede">
        The documents a trial is made of, and what each one is responsible for.
      </p>

      <section class="section">
        <p>
          Every document is a JSON file addressed by the SHA-256 of its exact bytes.
          Documents reference each other by that fingerprint and never by name, so a
          reference either resolves to the identical file or fails. This site serves
          the files it publishes byte for byte, re-checking each one against its
          fingerprint before sending it; it never re-encodes them, because a second
          encoding would be a second document.
        </p>
      </section>

      <section class="section">
        <h2>The documents</h2>
        <article :for={document <- @documents} class="entry">
          <div class="entry__head">
            <h3 class="entry__title">{document.name}</h3>
            <.protocol_badge name={document.schema} />
          </div>
          <p>{document.role}</p>
          <p :if={document.kind == :data_policy} class="small quiet">
            {publication_note()}
          </p>
          <p :if={shipped(@shipped, document)} class="small">
            In this release:
            <.digest
              value={shipped(@shipped, document).protocol_digest}
              href={"/api/v1/objects/" <> shipped(@shipped, document).protocol_digest}
            />
          </p>
        </article>
      </section>

      <section class="section">
        <h2>Reading the catalog directly</h2>
        <p>
          The catalog index lists every document this release publishes, with the
          fingerprint and location of each.
        </p>
        <.definition_list>
          <:fact term="The index">
            <a href="/api/v1/catalog">/api/v1/catalog</a>
          </:fact>
          <:fact term="One document">
            <span class="digest">/api/v1/objects/sha256:…</span>
          </:fact>
          <:fact term="One Climb, summarised">
            <span class="digest">/api/v1/climbs/…</span>
          </:fact>
          <:fact term="Installation details">
            <a href="/api/v1/bootstrap">/api/v1/bootstrap</a>
          </:fact>
          <:fact term="One published run">
            <span class="digest">/api/v1/submissions/sha256:…</span>
          </:fact>
          <:fact term="The key this site signs with">
            <a href="/api/v1/network-key">/api/v1/network-key</a>
          </:fact>
        </.definition_list>
        <p class="small quiet">
          Every one of these is a read. One address accepts something — <span class="digest">POST /api/v1/submissions</span>, where a person
          publishes a finished run of their own — and everything else refuses.
          There is no Techtree account to hold either way.
        </p>
      </section>

      <section class="section">
        <h2>Schemas</h2>
        <p>
          Each document states its schema version in a field of its own, shown beside
          its name above. The schema files themselves are maintained with the
          command-line tool rather than published here, so that there is exactly one
          copy of them and it is the one the tool validates against.
        </p>
      </section>
    </Layouts.page>
    """
  end

  defp shipped_objects do
    Query.list_objects()
    |> Enum.group_by(& &1.kind)
    |> Map.new(fn {kind, entries} -> {kind, hd(entries)} end)
  end

  defp shipped(_shipped, %{kind: nil}), do: nil
  defp shipped(shipped, %{kind: kind}), do: Map.get(shipped, kind)
end
