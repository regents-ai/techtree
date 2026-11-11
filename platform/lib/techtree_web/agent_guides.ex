defmodule TechtreeWeb.AgentGuides do
  @moduledoc """
  A page for each agent people pair with Techtree, at `/agents/SLUG`, and the list
  of them at `/agents`. Each agent is one committed Markdown file in
  `priv/public/agents/`, named by its slug: its harness value with `-` for `_`
  (`grok_bot` is `grok-bot`). Every file has one shape:

    * `# NAME`, then one line on how it pairs, which is also the page's search
      description and its line on `/agents`;
    * `## Set up`: what this agent needs beyond the Techtree skill. The Techtree
      skill (`TechtreeWeb.AgentSkills`) with this section added is the agent's own
      skill, at `/agents/SLUG/skill.md`;
    * `## Questions`, then `## Troubleshooting`, ending with its Patchbay link.

  Adding an agent is adding its file. Nothing here reads the database.
  """

  alias TechtreeWeb.AgentSkills

  @directory Application.app_dir(:techtree, "priv/public/agents")
  @files @directory |> Path.join("*.md") |> Path.wildcard() |> Enum.sort()
  for file <- @files, do: @external_resource(file)

  @guides Map.new(@files, fn file ->
            source = File.read!(file)
            ["# " <> name, rest] = String.split(source, "\n", parts: 2)
            [summary | _] = rest |> String.trim_leading() |> String.split("\n", parts: 2)
            [_, setup] = String.split(source, "\n## Set up\n", parts: 2)
            [setup | _] = String.split(setup, "\n## ", parts: 2)

            {Path.basename(file, ".md"),
             %{name: name, summary: summary, source: source, setup: String.trim(setup)}}
          end)

  # The agents the pairing box offers, as slugs, in its order.
  @slugs Enum.map(
           RegentAgents.Harness.featured(),
           &(&1 |> to_string() |> String.replace("_", "-"))
         )
  # Every agent the pairing box offers has a page, and every page is one it offers.
  @unmatched (@slugs -- Map.keys(@guides)) ++ (Map.keys(@guides) -- @slugs)
  if @unmatched != [],
    do: raise("priv/public/agents and Harness.featured/0 differ: #{inspect(@unmatched)}")

  # A new agent's file recompiles this module, as an edited one does.
  def __mix_recompile__?,
    do: @directory |> Path.join("*.md") |> Path.wildcard() |> Enum.sort() != @files

  @doc "The list of agents, then every agent's page."
  @spec paths() :: [String.t()]
  def paths, do: ["/agents" | Enum.map(@slugs, &("/agents/" <> &1))]

  @doc "The page at `path` as Markdown, or nil when it names no agent."
  @spec document(String.t()) :: %{title: String.t(), markdown: String.t()} | nil
  def document("/agents"), do: %{title: "Agents", markdown: fill(index())}

  def document("/agents/" <> slug) do
    case @guides do
      %{^slug => guide} -> %{title: guide.name, markdown: fill(guide.source)}
      _other -> nil
    end
  end

  @doc "The search description of the page at `path`."
  @spec description(String.t()) :: String.t() | nil
  def description("/agents"),
    do: "Each agent's pairing with Techtree: its setup, common questions and help."

  def description("/agents/" <> slug) do
    case @guides do
      %{^slug => guide} -> guide.summary
      _other -> nil
    end
  end

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

  defp index do
    lines =
      Enum.map_join(@slugs, "\n", fn slug ->
        guide = @guides[slug]
        "- [#{guide.name}]({{origin}}/agents/#{slug}): #{guide.summary}"
      end)

    """
    # Agents

    Your agent pairs with your Techtree account and works for you: it publishes and withdraws your Results and reads your Credits and Points. It can never use your wallet, change your account or pair other agents.

    1. Sign in, open [Pair New Agent]({{origin}}/account/agents) on your Agents page and choose your agent. Its pairing code works once, for ten minutes.
    2. Paste the message to your agent wherever you chat with it.
    3. It shows in your account menu under its name.

    Each page below is one agent's: how to set it up, answers to common questions and where to get help.

    #{lines}
    """
  end

  defp fill(markdown), do: String.replace(markdown, "{{origin}}", TechtreeWeb.Endpoint.url())
end
