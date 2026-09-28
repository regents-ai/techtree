defmodule Techtree.Capabilities do
  @moduledoc """
  Every tool Techtree's pages offer a browser's own agent, read at compile time
  from `priv/tool_manifest.json`. The browser code registers them from the same
  file; `/capabilities` serves the manifest, and the Docs page and `/llms.txt`
  list them from here.
  """

  @manifest_path Path.expand("../../priv/tool_manifest.json", __DIR__)
  @external_resource @manifest_path
  @manifest @manifest_path |> File.read!() |> Jason.decode!()
  @needs %{"none" => "Nothing"}

  @doc "The whole manifest."
  @spec manifest() :: map()
  def manifest, do: @manifest

  @doc "Every tool, in the manifest's order."
  @spec tools() :: [map()]
  def tools, do: @manifest["tools"]

  @doc "The tools every page registers."
  @spec site_tools() :: [map()]
  def site_tools, do: Enum.filter(tools(), &(&1["scope"] == "site"))

  @doc "What a tool needs from the person, in words."
  @spec needs(map()) :: String.t()
  def needs(tool), do: Map.fetch!(@needs, tool["requires"])

  @doc "Every tool as a Markdown table."
  @spec markdown_table() :: String.t()
  def markdown_table do
    """
    | Tool | Reads | Needs | What it does |
    | --- | --- | --- | --- |
    #{Enum.map_join(tools(), "\n", &"| `#{&1["name"]}` | `#{&1["route"]}` | #{needs(&1)} | #{&1["description"]} |")}\
    """
  end
end
