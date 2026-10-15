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
      id: :skill_test,
      name:
        "Test a Skill: make tasks from it, then compare with and without it, or with its earlier version",
      status: :experimental
    },
    %{
      id: :skill_revision,
      name: "Revise a Skill once and compare the revision with it",
      status: :experimental
    },
    %{
      id: :climb,
      name: "Try the Hello World Climb, a small fixed comparison with a starter Skill",
      status: :available
    },
    %{
      id: :frontier_climb,
      name: "Improve a Skill on ten open-ended Frontier-CS programming problems",
      status: :experimental
    },
    %{
      id: :browser_tools,
      name: "Tools for agents built into a browser (WebMCP)",
      status: :available
    },
    %{
      id: :hosted_building,
      name: "Hosted environment building (Repo2RLEnv service)",
      status: :planned
    },
    %{id: :mcp_connector, name: "An MCP connector for other agents", status: :planned},
    %{id: :nemo, name: "NVIDIA NeMo Fabric and NeMo Relay support", status: :planned}
  ]

  @doc "The actions a paired agent may take on its person's behalf."
  def may do
    [
      "Read your Credits balance, Credits history and Points",
      "Publish benchmark results with an independent publication proof",
      "Submit and read your Model Climb proofs"
    ]
  end

  @doc "The template pairing panel's names for this site's signed requests."
  def requests do
    [
      %{method: "GET", path: "/tools/account/balances", words: "Read Credits balance"},
      %{method: "POST", path: "/tools/account/credits/history", words: "Read Credits history"},
      %{method: "GET", path: "/tools/account/points", words: "Read Points"},
      %{method: "POST", path: "/api/v1/publications", words: "Submitted a signed publication"},
      %{
        method: "POST",
        path: "/api/model-climb/v1/reports",
        words: "Submitted a Model Climb proof"
      },
      %{method: "GET", path: "/api/model-climb/v1/reports", words: "Read Model Climb proofs"},
      %{
        method: "GET",
        path: "/api/model-climb/v1/reports/{digest}",
        words: "Read a Model Climb proof"
      }
    ]
  end

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
