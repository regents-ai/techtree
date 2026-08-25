defmodule TechtreeWeb.EvidenceGraph do
  @moduledoc """
  A truthful projection of the artifacts behind one published campaign.

  The baseline and candidate nodes are declared branches of the same immutable
  CampaignSpec. They deliberately say `declared`, not `completed`: a result is
  added only when a separately published proof supplies the receipts.
  """

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
  Build the campaign graph from an imported Climb projection.
  """
  @spec from_climb(map() | nil) :: [graph_node()]
  def from_climb(nil), do: []

  def from_climb(%{projection: facts}) do
    campaign_digest = facts["campaign_spec_digest"]
    validation_digest = facts["validation_receipt_digest"]
    model = model_coordinate(facts["subject_model"])
    harness = join([facts["subject_harness"], facts["subject_harness_version"]])
    task_count = value(facts["task_count"])
    run_budget = run_budget(facts["budget"])
    validation = facts["task_validation"] || %{}

    [
      %{
        id: "campaign",
        label: "Campaign",
        artifact: "CampaignSpec",
        digest: campaign_digest,
        href: object_url(campaign_digest),
        position: :root,
        status: :published,
        facts: [
          {"Status", "Published definition"},
          {"Tasks", task_count},
          {"Harness", harness},
          {"Model", model},
          {"Run ceiling", run_budget},
          {"Evidence", "Definition and task validation are present"}
        ]
      },
      %{
        id: "baseline",
        label: "Baseline",
        artifact: "CampaignSpec baseline branch",
        digest: campaign_digest,
        href: object_url(campaign_digest),
        position: :left,
        status: :declared,
        facts: [
          {"Status", "Declared; no public run receipt"},
          {"Score", "Not run in this public record"},
          {"Tasks", task_count},
          {"Harness", harness},
          {"Model", model},
          {"Skill digest", "No Skill in the baseline branch"},
          {"Run ceiling", run_budget},
          {"Evidence", "Campaign definition only"}
        ]
      },
      %{
        id: "candidate",
        label: "Candidate",
        artifact: "CampaignSpec candidate branch",
        digest: campaign_digest,
        href: object_url(campaign_digest),
        position: :right,
        status: :declared,
        facts: [
          {"Status", "Declared; no public run receipt"},
          {"Score", "Not run in this public record"},
          {"Tasks", task_count},
          {"Harness", harness},
          {"Model", model},
          {"Skill digest", "Recorded when a participant supplies the Skill"},
          {"Run ceiling", run_budget},
          {"Evidence", "Campaign definition only"}
        ]
      },
      %{
        id: "validation",
        label: "Task validation",
        artifact: "TasksetValidationReceipt",
        digest: validation_digest,
        href: object_url(validation_digest),
        position: :merge,
        status: validation_status(validation),
        facts: [
          {"Status", validation_words(validation)},
          {"Tasks", validation_count(validation, task_count)},
          {"Harness", "Publisher validation"},
          {"Model", "No model call"},
          {"Skill digest", "Not applicable"},
          {"Model calls", "None"},
          {"Evidence", "Signed publisher receipt in the active catalog"}
        ]
      }
    ]
  end

  defp model_coordinate(model) when is_map(model) do
    join([model["provider"], model["model_id"], model["revision"]])
  end

  defp model_coordinate(_model), do: "Not published"

  defp run_budget(%{"maximum_model_calls" => calls}) when is_integer(calls),
    do: "#{calls} model calls maximum"

  defp run_budget(_budget), do: "Not published"

  defp validation_status(%{"status" => "valid"}), do: :complete
  defp validation_status(_validation), do: :unavailable

  defp validation_words(%{"status" => "valid"}), do: "Complete"
  defp validation_words(_validation), do: "Unavailable"

  defp validation_count(%{"valid" => valid, "total" => total}, _fallback)
       when is_integer(valid) and is_integer(total),
       do: validation_count_words(valid, total)

  defp validation_count(_validation, fallback), do: fallback

  defp validation_count_words(total, total), do: "#{total} tasks validated"
  defp validation_count_words(valid, total), do: "#{valid} of #{total} tasks valid"

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
