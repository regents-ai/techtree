defmodule TechtreeWeb.ClimbCopy do
  @moduledoc """
  The published names a Climb is presented under that no protocol document
  carries.

  A ClimbManifest has a title and a summary. A CampaignSpec has neither, and
  nothing in the protocol names the task family in words, the Skill a newcomer
  starts from, or what the results of a run are called. Those are decisions
  about how a published Climb is described, so they are written once, here,
  against the reference they belong to, and never inferred from a package name
  or a file path.

  A Climb with no entry is described from its own documents and nothing else.
  """

  @type t :: %{
          subtitle: String.t(),
          scope: String.t(),
          campaign_title: String.t(),
          task_family: String.t(),
          starter_skill: String.t(),
          starter_note: String.t(),
          first_result_label: String.t(),
          second_result_label: String.t(),
          revision_note: String.t()
        }

  @copy %{
    "hello-world-climb@1" => %{
      subtitle: "A toy Skill-uplift Climb",
      scope:
        "A toy introductory demonstration of the mechanism, not a measure of broad capability.",
      campaign_title: "Hello World Skill Uplift",
      task_family: "BranchCode v1",
      starter_skill: "hello-world-starter-v1",
      starter_note:
        "The Hello World starter Skill is intentionally incomplete and calibrated " <>
          "to solve roughly two-thirds of the toy tasks. Individual runs may vary. " <>
          "The gap is deliberate, so that the guided one-turn revision has " <>
          "measurable headroom.",
      first_result_label: "Hello World Uplift Receipt",
      second_result_label: "Hello World — Iteration 2",
      revision_note:
        "Your own agent proposes one revision. Techtree tests it exactly the way it " <>
          "tested the first attempt. A proposal may be unusable, or may run and fail to " <>
          "improve the score — both of those are results, and both are reported as they " <>
          "happened."
    }
  }

  @doc """
  The published copy for one Climb reference, or `nil` when this release
  publishes none for it.
  """
  @spec for_reference(term()) :: t() | nil
  def for_reference(reference), do: Map.get(@copy, reference)
end
