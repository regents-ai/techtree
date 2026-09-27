defmodule TechtreeWeb.Tools do
  @moduledoc """
  The tools every page offers a browser's own agent, read at compile time from
  `priv/tool_manifest.json`. The browser code registers them from the same
  file; the Docs page and `/llms.txt` list them from here.
  """

  @path Path.expand("../../priv/tool_manifest.json", __DIR__)
  @external_resource @path
  @tools @path |> File.read!() |> Jason.decode!() |> Map.fetch!("tools")
  @needs %{"none" => "Nothing"}

  @doc "Every tool, in the manifest's order."
  @spec all() :: [map()]
  def all, do: @tools

  @doc "What a tool needs from the person, in words."
  @spec needs(map()) :: String.t()
  def needs(tool), do: Map.fetch!(@needs, tool["requires"])

  @doc "The tools as a Markdown table."
  @spec markdown_table() :: String.t()
  def markdown_table do
    """
    | Tool | Reads | Needs | What it does |
    | --- | --- | --- | --- |
    #{Enum.map_join(@tools, "\n", &"| `#{&1["name"]}` | `#{&1["route"]}` | #{needs(&1)} | #{&1["description"]} |")}\
    """
  end
end
