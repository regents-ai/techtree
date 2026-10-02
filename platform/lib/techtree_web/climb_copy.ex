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
          candidate_skill_label: String.t(),
          result_note: %{text: String.t(), bundle_digest: String.t()} | nil
        }

  # A Climb that moves to a new version without changing its tasks, model or
  # starter Skill keeps its copy, and its earlier version keeps it too for the
  # Results published against it.
  @hello_world %{
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
    candidate_skill_label: "Hello World Skill",
    result_note: nil
  }

  @frontier_cs %{
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
      "A problem statement. The agent writes a C++17 program, which is run on each of the " <>
        "problem's 10 test inputs.",
    output: "For each test input, an answer that keeps every rule of the problem.",
    scoring:
      "Each test input scores from 0 to 1 by the problem's own checker, and 0 when the " <>
        "program breaks a rule, fails to compile, crashes or runs over the problem's time " <>
        "or memory limit. A problem scores the mean of its 10 inputs; the Climb, the mean " <>
        "of its 10 problems.",
    held_fixed:
      "Problems and their order, test inputs, checkers, compiler, each problem's time and " <>
        "memory limits, model, Hermes harness, runtime, tools, sampling, and budget.",
    campaign_title: "Frontier-CS Open-Ended Skill Uplift",
    candidate_skill_label: "Frontier-CS Skill",
    result_note: %{
      text:
        "The first run, with the original starter Skill, scored 0.043 with it against " <>
          "0.128 without it. With the rewritten starter Skill, a second run still scored " <>
          "lower than no Skill, though by less: a mean of 0.100 with it against 0.131 " <>
          "without it, better on two problems and worse on three.",
      bundle_digest: "sha256:345e4151ce3039f01537a1a77bc5b8954c42c37e17e7f95f8ca3a177475e2155"
    }
  }

  @tasksmith %{
    scope:
      "Six real changes from Hugging Face's trl, transformers, diffusers, peft and " <>
        "accelerate repositories, from the HF ML Tasksmith collection. With thanks to its " <>
        "authors. Not a measure of broad capability.",
    introduction:
      "six real changes from Hugging Face's Python libraries, each scored by the change's " <>
        "own tests",
    question:
      "Does adding the Tasksmith Skill solve more of 6 real changes to Hugging Face code?",
    input:
      "A repository with one real change taken back out, and a description of the change " <>
        "to make. Each task brings its own image.",
    output: "The repository's files with the change made again.",
    scoring:
      "Solved: the change's own tests run in a separate box on only the files the task " <>
        "names. Each task is 0 or 1, then the 6 task values are averaged.",
    held_fixed:
      "Tasks and their order, each task's own images for working and for grading, model, " <>
        "Hermes harness, tools, sampling, and budget.",
    campaign_title: "HF Tasksmith Skill Uplift",
    candidate_skill_label: "Tasksmith Skill",
    result_note: nil
  }

  @copy %{
    "hello-world-climb@1" => @hello_world,
    "hello-world-climb@2" => @hello_world,
    "frontier-cs-open-ended-climb@1" => @frontier_cs,
    "frontier-cs-open-ended-climb@2" => @frontier_cs,
    "tasksmith-climb@1" => @tasksmith
  }

  @doc """
  The published copy for one Climb reference, or `nil` when this release
  publishes none for it.
  """
  @spec for_reference(term()) :: t() | nil
  def for_reference(reference), do: Map.get(@copy, reference)
end
