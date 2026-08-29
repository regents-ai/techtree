defmodule TechtreeWeb.EvidenceGraph do
  @moduledoc """
  A truthful projection of the artifacts behind one published campaign.

  Every catalog node is an object this site serves under a content address, and
  every fact inside one is read from those bytes. Published proof nodes link to
  the public run-log receipts instead. Nothing here is illustrative: a branch
  that has been declared says `declared`, while proof links appear only when
  the run log contains them.

  That is the whole discipline of this module. A graph is the most persuasive
  thing on a page, so it is the last place an invented number belongs.
  """

  alias TechtreeWeb.CampaignFacts
  @type fact :: {String.t(), String.t()}
  @type link :: {String.t(), String.t()}
  @type proof_set :: %{entries: [map()], truncated?: boolean()}
  @type graph_node :: %{
          artifact: String.t(),
          digest: String.t() | nil,
          facts: [fact()],
          href: String.t() | nil,
          id: String.t(),
          label: String.t(),
          links: [link()],
          position: atom(),
          status: atom()
        }

  @doc """
  Build the campaign graph from an imported Climb and the active release.

  The release is optional: without one, the branch that mounts a Skill says
  that the Skill is supplied by the participant, which is what is true.

  Published proofs are supplied separately because they belong to the public
  run log rather than the imported Campaign catalog. The list may be empty,
  contain one proof, or contain many; the graph describes whichever state the
  log is actually in.
  """
  @spec from_climb(map() | nil, map() | nil, [map()] | proof_set()) :: [graph_node()]
  def from_climb(climb, release \\ nil, published_proofs \\ [])

  def from_climb(nil, _release, _published_proofs), do: []

  def from_climb(%{projection: facts} = climb, release, published_proofs) do
    published = CampaignFacts.for_climb(climb)
    proof_set = normalize_proof_set(published_proofs)

    shared = [
      {"Tasks",
       CampaignFacts.membership_words(published.membership) || value(facts["task_count"])},
      {"Subject harness", join([facts["subject_harness"], facts["subject_harness_version"]])},
      {"Subject model", model_coordinate(facts["subject_model"])},
      {"Per-branch ceiling", CampaignFacts.budget_words(published.budget) || "Not published"}
    ]

    [campaign_node(facts, shared)] ++
      validation_node(facts, published.validation) ++
      [
        baseline_node(facts),
        candidate_node(facts, release),
        proofs_node(proof_set)
      ]
  end

  def from_climb(_climb, _release, _published_proofs), do: []

  # -- The nodes ------------------------------------------------------------

  defp campaign_node(facts, shared) do
    digest = facts["campaign_spec_digest"]

    %{
      id: "campaign",
      label: "Campaign",
      artifact: "The published campaign definition",
      digest: digest,
      href: object_url(digest),
      position: :root,
      status: :published,
      links: [],
      facts:
        [{"Status", "Published definition"}] ++
          shared ++
          [{"Evidence", "Definition and task validation are present"}]
    }
  end

  defp baseline_node(facts) do
    digest = facts["campaign_spec_digest"]

    %{
      id: "baseline",
      label: "Baseline",
      artifact: "The baseline branch of that definition",
      digest: digest,
      href: object_url(digest),
      position: :left,
      status: :declared,
      links: [],
      facts: [
        {"Status", "Declared branch"},
        {"Skill", "No Skill in the baseline branch"},
        {"Source", "Campaign definition"}
      ]
    }
  end

  defp candidate_node(facts, release) do
    digest = facts["campaign_spec_digest"]

    %{
      id: "candidate",
      label: "Candidate",
      artifact: "The candidate branch of that definition",
      digest: digest,
      href: object_url(digest),
      position: :right,
      status: :declared,
      links: [],
      facts:
        [{"Status", "Declared branch"}] ++
          candidate_skill_facts(release) ++ [{"Source", "Campaign definition"}]
    }
  end

  defp validation_node(_facts, validation) when map_size(validation) == 0, do: []

  defp validation_node(facts, validation) do
    digest = facts["validation_receipt_digest"]

    [
      %{
        id: "validation",
        label: "Task validation",
        artifact: "The content-addressed task validation object",
        digest: digest,
        href: object_url(digest),
        position: :checkpoint,
        status: validation_status(validation),
        links: [],
        facts: [
          {"Status", validation_words(validation)},
          {"Tasks", CampaignFacts.validation_words(validation) || "Not published"},
          {"Method", "No model call"},
          {"Evidence", "Digest-addressed catalog object"}
        ]
      }
    ]
  end

  defp proofs_node(%{entries: proofs} = proof_set) do
    %{
      id: "proofs",
      label: "Published proofs",
      artifact: "Recorded proof receipts for this Campaign",
      digest: nil,
      href: nil,
      position: :merge,
      status: if(proofs == [], do: :unavailable, else: :published),
      links: proof_links(proofs),
      facts: [
        {"Status", proof_status(proof_set)},
        {"Evidence", "Server-checked proof bundles, signed by participants"}
      ]
    }
  end

  # -- Words ----------------------------------------------------------------

  defp candidate_skill_facts(%{starter_skill: %{"name" => name, "tree_digest" => digest}})
       when is_binary(name) and is_binary(digest) do
    [{"Skill", "Starts from #{name}"}, {"Skill tree digest", digest}]
  end

  defp candidate_skill_facts(_release), do: [{"Skill", "Supplied by the participant"}]

  defp normalize_proof_set(%{entries: entries, truncated?: truncated?}),
    do: %{entries: entries, truncated?: truncated?}

  defp normalize_proof_set(proofs) when is_list(proofs), do: %{entries: proofs, truncated?: false}

  defp active_proofs(proofs), do: Enum.reject(proofs, &Map.get(&1, :withdrawn_at))

  defp proof_status(%{entries: [], truncated?: false}), do: "No published proofs yet"

  defp proof_status(%{entries: proofs, truncated?: true}) do
    "Showing #{length(proofs)} most recent proofs"
  end

  defp proof_status(%{entries: proofs, truncated?: false}) do
    active_count = length(active_proofs(proofs))
    withdrawn_count = length(proofs) - active_count

    recorded_words =
      "#{length(proofs)} recorded proof" <> if(length(proofs) == 1, do: "", else: "s")

    withdrawn_words =
      if(withdrawn_count == 0, do: nil, else: "#{withdrawn_count} withdrawn")

    [recorded_words, withdrawn_words]
    |> Enum.reject(&is_nil/1)
    |> Enum.join(" · ")
  end

  defp proof_links(proofs) do
    Enum.map(proofs, fn proof ->
      {
        proof_label(proof),
        "/results/" <> proof.bundle_digest
      }
    end)
  end

  defp proof_label(proof) do
    prefix = if(Map.get(proof, :withdrawn_at), do: "Withdrawn · ", else: "")
    prefix <> "#{proof.wins} better · #{proof.ties} same · #{proof.losses} worse"
  end

  defp validation_status(%{"status" => "valid"}), do: :complete
  defp validation_status(_validation), do: :unavailable

  defp validation_words(%{"status" => "valid"}), do: "Complete"
  defp validation_words(_validation), do: "Unavailable"

  defp model_coordinate(model) when is_map(model) do
    join([model["provider"], model["model_id"], model["revision"]])
  end

  defp model_coordinate(_model), do: "Not published"

  defp object_url(digest) when is_binary(digest), do: "/api/v1/objects/" <> digest
  defp object_url(_digest), do: "#"

  defp join(parts) do
    parts
    |> Enum.reject(&(&1 in [nil, ""]))
    |> Enum.join(" · ")
    |> case do
      "" -> "Not published"
      value -> value
    end
  end

  defp value(nil), do: "Not published"
  defp value(value), do: to_string(value)
end
