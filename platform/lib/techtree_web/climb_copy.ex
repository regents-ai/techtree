defmodule TechtreeWeb.ClimbCopy do
  @moduledoc """
  The published names a Climb is presented under that no protocol document
  carries.

  A ClimbManifest has a title and a summary. A CampaignSpec has neither, and
  nothing in the protocol names the task family in words or the Skill a
  newcomer starts from. Those are decisions about how a published Climb is
  described, so they are written once, here, against the reference they belong
  to, and never inferred from a package name or a file path.

  A Climb with no entry is described from its own documents and nothing else.
  """

  @type t :: %{
          subtitle: String.t(),
          scope: String.t(),
          introduction: String.t(),
          question: String.t(),
          input: String.t(),
          output: String.t(),
          scoring: String.t(),
          held_fixed: String.t(),
          campaign_title: String.t(),
          task_family: String.t(),
          starter_skill: String.t(),
          candidate_skill_label: String.t()
        }

  @copy %{
    "hello-world-climb@1" => %{
      subtitle: "A toy Skill-uplift Climb",
      scope:
        "A toy introductory demonstration of the mechanism, not a measure of broad capability.",
      introduction:
        "a small demonstration of how a Climb works rather than a measure of broad capability",
      question:
        "Does adding the Hello World Skill improve exact-match scores across 36 fixed tasks?",
      input: "A short lowercase string for each task.",
      output: "One exact answer token and no additional text.",
      scoring: "Exact match: each task is 0 or 1, then the 36 task values are averaged.",
      held_fixed:
        "Task membership and order, model, Hermes harness, runtime, tools, sampling, and budget.",
      campaign_title: "Hello World Skill Uplift",
      task_family: "BranchCode v1",
      starter_skill: "hello-world-starter-v1",
      candidate_skill_label: "Hello World Skill"
    }
  }

  @doc """
  The published copy for one Climb reference, or `nil` when this release
  publishes none for it.
  """
  @spec for_reference(term()) :: t() | nil
  def for_reference(reference), do: Map.get(@copy, reference)
end
