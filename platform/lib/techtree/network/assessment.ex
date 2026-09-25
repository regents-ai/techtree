defmodule Techtree.Network.Assessment do
  @moduledoc """
  What this site worked out about one published Result, stored with it.

  `Techtree.Network.Result` recomputes it from the signed report and the
  Campaign when the Result is published, and the Result's page reads it from
  here rather than checking the stored bundle again on every visit.

  The totals are exact decimals: the sum of each run's task scores, each read
  as the decimal its JSON number carries. A mean is a total over the task
  count, so a page can show one without anything having been rounded on the
  way in.
  """

  use Ash.Resource, data_layer: :embedded

  alias Techtree.Network.Assessment.SkillChange

  @reasons [
    :cleared_rule,
    :fell_past_rule,
    :rose_short_of_rule,
    :unchanged,
    :fell_short_of_rule,
    :no_rule
  ]

  actions do
    defaults [:read, create: :*]
  end

  attributes do
    attribute :reason, :atom do
      description "Why the verdict is what it is, in terms of the Campaign's rule."
      allow_nil? false
      public? true
      constraints one_of: @reasons
    end

    attribute :baseline_total, :decimal do
      description "The exact sum of the task scores without the Skill."
      allow_nil? false
      public? true
    end

    attribute :candidate_total, :decimal do
      description "The exact sum of the task scores with the Skill."
      allow_nil? false
      public? true
    end

    attribute :task_count, :integer do
      description "How many tasks both runs scored."
      allow_nil? false
      public? true
      constraints min: 1
    end

    attribute :minimum, :decimal do
      description "The smallest change in the mean the Campaign's rule accepts."
      allow_nil? false
      public? true
    end

    attribute :wins, :integer do
      description "Tasks the Skill scored higher on."
      allow_nil? false
      public? true
      constraints min: 0
    end

    attribute :losses, :integer do
      description "Tasks the Skill scored lower on."
      allow_nil? false
      public? true
      constraints min: 0
    end

    attribute :ties, :integer do
      description "Tasks both runs scored the same on."
      allow_nil? false
      public? true
      constraints min: 0
    end

    attribute :model_build_unproven, :boolean do
      description "Whether the Campaign's model names no build, so the runs share a model name only."
      allow_nil? false
      public? true
    end

    attribute :skill_changes, {:array, SkillChange} do
      description "Every difference the signed report found between the two runs' settings."
      allow_nil? false
      public? true
      constraints min_length: 1
    end
  end
end
