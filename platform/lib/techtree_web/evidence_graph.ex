defmodule TechtreeWeb.EvidenceGraph do
  @moduledoc """
  A truthful projection of the artifacts behind one published campaign.

  Every node is an object this site serves under a content address, and every
  fact inside a node is read from those bytes. Nothing here is illustrative: a
  node that would need a run receipt to exist is not drawn, and a branch that
  has been declared but never run says `declared` rather than `done`.

  That is the whole discipline of this module. A graph is the most persuasive
  thing on a page, so it is the last place an invented number belongs.
  """

  alias TechtreeWeb.CampaignFacts
  alias TechtreeWeb.ClimbCopy

  @type fact :: {String.t(), String.t()}
  @type graph_node :: %{
          artifact: String.t(),
          digest: String.t(),
          facts: [fact()],
          href: String.t(),
          id: String.t(),
          label: String.t(),
          position: atom(),
          status: atom()
        }

  @doc """
  Build the campaign graph from an imported Climb and the active release.

  The release is optional: without one, the branch that mounts a Skill says
  that the Skill is supplied by the participant, which is what is true.
  """
  @spec from_climb(map() | nil, map() | nil) :: [graph_node()]
  def from_climb(climb, release \\ nil)

  def from_climb(nil, _release), do: []

  def from_climb(%{projection: facts} = climb, release) do
    published = CampaignFacts.for_climb(climb)
    copy = ClimbCopy.for_reference(climb.reference)

    shared = [
      {"Tasks",
       CampaignFacts.membership_words(published.membership) || value(facts["task_count"])},
      {"Harness", join([facts["subject_harness"], facts["subject_harness_version"]])},
      {"Model", model_coordinate(facts["subject_model"])},
      {"Run ceiling", CampaignFacts.budget_words(published.budget) || "Not published"}
    ]

    [
      campaign_node(facts, shared),
      baseline_node(facts, shared),
      candidate_node(facts, shared, release, copy)
    ] ++ validation_node(facts, published.validation)
  end

  def from_climb(_climb, _release), do: []

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
      facts:
        [{"Status", "Published definition"}] ++
          shared ++
          [{"Evidence", "Definition and task validation are present"}]
    }
  end

  defp baseline_node(facts, shared) do
    digest = facts["campaign_spec_digest"]

    %{
      id: "baseline",
      label: "Baseline",
      artifact: "The baseline branch of that definition",
      digest: digest,
      href: object_url(digest),
      position: :left,
      status: :declared,
      facts:
        [{"Status", "Declared; no public run receipt"}] ++
          shared ++
          [
            {"Skill", "No Skill in the baseline branch"},
            {"Evidence", "Campaign definition only"}
          ]
    }
  end

  defp candidate_node(facts, shared, release, copy) do
    digest = facts["campaign_spec_digest"]

    %{
      id: "candidate",
      label: "Candidate",
      artifact: "The candidate branch of that definition",
      digest: digest,
      href: object_url(digest),
      position: :right,
      status: :declared,
      facts:
        [{"Status", "Declared; no public run receipt"}] ++
          shared ++
          [
            {"Skill", starter_skill_words(release)},
            {"Score band", (copy && copy.starter_note) || "Not published"},
            {"Evidence", "Campaign definition only"}
          ]
    }
  end

  defp validation_node(_facts, validation) when map_size(validation) == 0, do: []

  defp validation_node(facts, validation) do
    digest = facts["validation_receipt_digest"]

    [
      %{
        id: "validation",
        label: "Task validation",
        artifact: "The publisher’s signed check of the tasks",
        digest: digest,
        href: object_url(digest),
        position: :merge,
        status: validation_status(validation),
        facts: [
          {"Status", validation_words(validation)},
          {"Tasks", CampaignFacts.validation_words(validation) || "Not published"},
          {"Model", "No model call"},
          {"Skill", "Not applicable"},
          {"Evidence", "Signed publisher receipt in the active release"}
        ]
      }
    ]
  end

  # -- Words ----------------------------------------------------------------

  defp starter_skill_words(%{starter_skill: %{"name" => name, "tree_digest" => digest}})
       when is_binary(name) and is_binary(digest) do
    "Starts from #{name} · #{digest}"
  end

  defp starter_skill_words(_release), do: "Supplied when a participant prepares the run"

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
