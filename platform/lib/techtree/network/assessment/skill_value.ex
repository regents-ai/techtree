defmodule Techtree.Network.Assessment.SkillValue do
  @moduledoc """
  One side of one Skill difference: no Skill, a field that is not set, a whole
  Skill by fingerprint and size, or one field's fingerprint, size or text.
  """

  use Ash.Resource, data_layer: :embedded

  actions do
    defaults [:read, create: :*]
  end

  attributes do
    attribute :kind, :atom do
      description "Which of the shapes below this side is."
      allow_nil? false
      public? true
      constraints one_of: [:none, :not_set, :skill, :digest, :size, :text]
    end

    attribute :digest, :string do
      description "The fingerprint, for a whole Skill or its fingerprint field."
      public? true
    end

    attribute :size, :integer do
      description "The size in bytes, for a whole Skill or its size field."
      public? true
      constraints min: 1
    end

    attribute :text, :string do
      description "The text of a file type or file name field."
      public? true
    end
  end
end
