defmodule TechtreeWeb.Capabilities do
  @moduledoc """
  What Techtree can do, and how ready each part is.

  Every page that names a capability shows its status from here, in one of
  three words — Available now, Experimental, Planned — so two pages cannot
  disagree about the same thing.
  """

  @type status :: :available | :experimental | :planned
  @type capability :: %{id: atom(), name: String.t(), status: status()}

  @capabilities [
    %{
      id: :climb,
      name: "Compare with and without a Skill on a fixed challenge (Climb)",
      status: :available
    },
    %{id: :skill_environment, name: "Create an environment from a Skill", status: :experimental},
    %{id: :repository_tasks, name: "Build tasks from a repository", status: :experimental},
    %{
      id: :skill_revision,
      name: "Revise a Skill once and compare the revision with it",
      status: :experimental
    },
    %{
      id: :hosted_building,
      name: "Hosted environment building (Repo2RLEnv service)",
      status: :planned
    },
    %{id: :nemo, name: "NVIDIA NeMo Fabric and NeMo Relay support", status: :planned},
    %{id: :agent_connectors, name: "Agent connectors (MCP, WebMCP)", status: :planned}
  ]

  @doc "Every capability, in the order pages list them."
  @spec all() :: [capability()]
  def all, do: @capabilities

  @doc "How ready one capability is."
  @spec status(atom()) :: status()
  for %{id: id, status: status} <- @capabilities do
    def status(unquote(id)), do: unquote(status)
  end

  @doc "The words a page shows for a status."
  @spec label(status()) :: String.t()
  def label(:available), do: "Available now"
  def label(:experimental), do: "Experimental"
  def label(:planned), do: "Planned"
end
