defmodule TechtreeWeb.ClimbCopy do
  @moduledoc """
  The published names a Climb is presented under that no protocol document
  carries.

  A ClimbManifest has a title and a summary. A CampaignSpec has neither, and
  nothing in the protocol says in words what a Climb asks, what its tasks take
  and give back, or where its tasks came from. Those are decisions about how a
  published Climb is described, so they are written once, here, against the
  reference they belong to, and never inferred from a package name or a file
  path.

  A Climb with no entry is described from its own documents and nothing else.
  """

  @type t :: %{
          scope: String.t(),
          introduction: String.t(),
          question: String.t(),
          input: String.t(),
          output: String.t(),
          scoring: String.t(),
          held_fixed: String.t(),
          campaign_title: String.t(),
          candidate_skill_label: String.t()
        }

  @copy %{
    "hello-world-climb@1" => %{
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
      candidate_skill_label: "Hello World Skill"
    },
    "frontier-cs-open-ended-climb@1" => %{
      scope:
        "Ten open-ended optimisation problems with no known best answer, from Frontier-CS " <>
          "(MIT licence) as chosen by the FrontierSmith authors. With thanks to both.",
      introduction:
        "ten open-ended programming problems with no known best answer, where every " <>
          "better answer scores higher",
      question:
        "Does adding the Frontier-CS Skill raise the mean score across 10 open-ended " <>
          "optimisation problems?",
      input:
        "A problem statement. The agent writes a C++17 program that reads each of the " <>
          "problem's 10 test files.",
      output: "For each test file, an answer that keeps every rule of the problem.",
      scoring:
        "Each test file scores from 0 to 1 by the problem's own checker, and 0 when a rule " <>
          "is broken. A problem scores the mean of its 10 files; the Climb, the mean of its " <>
          "10 problems.",
      held_fixed:
        "Problems and their order, test files, checkers, compiler, time and memory limits, " <>
          "model, Hermes harness, runtime, tools, sampling, and budget.",
      campaign_title: "Frontier-CS Open-Ended Skill Uplift",
      candidate_skill_label: "Frontier-CS Skill"
    }
  }

  @doc """
  The published copy for one Climb reference, or `nil` when this release
  publishes none for it.
  """
  @spec for_reference(term()) :: t() | nil
  def for_reference(reference), do: Map.get(@copy, reference)
end
