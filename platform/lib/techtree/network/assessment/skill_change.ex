defmodule Techtree.Network.Assessment.SkillChange do
  @moduledoc """
  One difference between the two runs' settings: a whole Skill, or one field
  of one, with what each run had.
  """

  use Ash.Resource, data_layer: :embedded

  alias Techtree.Network.Assessment.SkillValue

  actions do
    defaults [:read, create: :*]
  end

  attributes do
    attribute :skill, :integer do
      description "The Skill's place in the list, counting from zero."
      allow_nil? false
      public? true
      constraints min: 0
    end

    attribute :field, :string do
      description "The field that differs, or nothing when the whole Skill does."
      public? true
      constraints allow_empty?: false
    end

    attribute :without, SkillValue do
      description "What the run without the Skill had."
      allow_nil? false
      public? true
    end

    attribute :with, SkillValue do
      description "What the run with the Skill had."
      allow_nil? false
      public? true
    end
  end
end
