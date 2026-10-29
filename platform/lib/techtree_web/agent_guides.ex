defmodule TechtreeWeb.AgentGuides do
  @moduledoc """
  The skill of each agent people pair with Techtree, at `/agents/SLUG/skill.md`:
  the Techtree skill (`TechtreeWeb.AgentSkills`) with that agent's Set up section
  added. Each agent is one committed Markdown file in `priv/public/agents/`, named
  by its slug: its harness value with `-` for `_` (`grok_bot` is `grok-bot`). Every
  file has one shape: `# NAME`, then `## Set up`, what this agent needs beyond the
  Techtree skill. Adding an agent is adding its file. Nothing here reads the
  database.
  """

  alias TechtreeWeb.AgentSkills

  @directory Application.app_dir(:techtree, "priv/public/agents")
  @files @directory |> Path.join("*.md") |> Path.wildcard() |> Enum.sort()
  for file <- @files, do: @external_resource(file)

  @guides Map.new(@files, fn file ->
            source = File.read!(file)
            ["# " <> name, rest] = String.split(source, "\n", parts: 2)
            [_, setup] = String.split(rest, "\n## Set up\n", parts: 2)
            {Path.basename(file, ".md"), %{name: name, setup: String.trim(setup)}}
          end)

  # The agents the pairing box offers, as slugs.
  @slugs Enum.map(
           RegentAgents.Harness.featured(),
           &(&1 |> to_string() |> String.replace("_", "-"))
         )
  # Every agent the pairing box offers has a skill, and every skill is one it offers.
  @unmatched (@slugs -- Map.keys(@guides)) ++ (Map.keys(@guides) -- @slugs)
  if @unmatched != [],
    do: raise("priv/public/agents and Harness.featured/0 differ: #{inspect(@unmatched)}")

  # A new agent's file recompiles this module, as an edited one does.
  def __mix_recompile__?,
    do: @directory |> Path.join("*.md") |> Path.wildcard() |> Enum.sort() != @files

  @doc "The agent's skill: the Techtree skill with its Set up section added, or nil."
  @spec skill(String.t()) :: String.t() | nil
  def skill(slug) do
    case @guides do
      %{^slug => guide} ->
        AgentSkills.skill_guide() <>
          "\n## On #{guide.name}\n\n" <> fill(guide.setup) <> "\n"

      _other ->
        nil
    end
  end

  defp fill(markdown), do: String.replace(markdown, "{{origin}}", TechtreeWeb.Endpoint.url())
end
