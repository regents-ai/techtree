defmodule TechtreeWeb.ResultNames do
  @moduledoc """
  What a published Result is called wherever a list or card names it: its
  Skill, its Climb, and the harness and model it ran with.

  The Skill's name may come from the publisher beside the signed bundle, so a
  page that shows it also says whose word it is. A Result published without a
  name takes the one its Climb gives its starter Skill.
  """

  alias Techtree.Network.AgentVersions
  alias TechtreeWeb.ClimbCopy

  @doc "The Skill a Result measured."
  @spec skill(map()) :: String.t()
  def skill(entry) do
    present(Map.get(entry, :skill_name)) || Map.get(copy(entry), :candidate_skill_label) ||
      "the candidate Skill"
  end

  @doc "The Climb a Result, or a challenge chosen among Results, belongs to."
  @spec campaign(map()) :: String.t()
  def campaign(entry) do
    present(Map.get(entry, :campaign_name)) || Map.get(copy(entry), :campaign_title) ||
      entry.climb_reference
  end

  @doc "The Climb, harness and model one Result ran with, in one line."
  @spec coordinates(map()) :: String.t()
  def coordinates(entry) do
    "#{campaign(entry)} · #{AgentVersions.label(entry.subject_harness)} " <>
      "#{entry.subject_harness_version} · #{entry.subject_model}"
  end

  defp copy(entry), do: ClimbCopy.for_reference(entry.climb_reference) || %{}

  defp present(value) when is_binary(value) do
    if String.trim(value) == "", do: nil, else: value
  end

  defp present(_value), do: nil
end
