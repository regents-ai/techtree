defmodule TechtreeWeb.EvidenceGraphTest do
  @moduledoc """
  The graph is the most persuasive thing on the site, so the rule it is held to
  is the strictest one: every node addresses a document this release actually
  serves, and no node carries a number that a run would have had to produce.
  """

  use TechtreeWeb.ConnCase, async: false

  alias Techtree.Catalog.Importer
  alias Techtree.Catalog.Query
  alias Techtree.CatalogFixture
  alias TechtreeWeb.EvidenceGraph
  alias TechtreeWeb.ReleaseInfo

  setup do
    CatalogFixture.use_bundle(CatalogFixture.root())
    :ok
  end

  test "no campaign draws no graph" do
    assert EvidenceGraph.from_climb(nil, nil) == []
  end

  test "every node addresses a document the site serves" do
    Importer.import!(CatalogFixture.root())
    nodes = graph()

    assert Enum.map(nodes, & &1.id) == ["campaign", "baseline", "candidate", "validation"]

    for node <- nodes do
      assert {:ok, _bytes, _entry} = Query.object_bytes(node.digest)
      assert node.href == "/api/v1/objects/" <> node.digest
    end
  end

  test "a branch that has not run says so, and carries no score" do
    Importer.import!(CatalogFixture.root())
    nodes = graph()

    for id <- ["baseline", "candidate"] do
      node = Enum.find(nodes, &(&1.id == id))

      assert node.status == :declared
      assert {"Status", "Declared; no public run receipt"} in node.facts
    end

    for node <- nodes, {_term, value} <- node.facts do
      refute value =~ ~r/\b\d{1,3}\s*(\/|out of)\s*36\b/
      refute value =~ ~r/\b\d{1,3}\s*%/
    end
  end

  test "the published check is the only node that says complete" do
    Importer.import!(CatalogFixture.root())
    nodes = graph()
    validation = Enum.find(nodes, &(&1.id == "validation"))

    assert validation.status == :complete
    assert {"Tasks", "36 tasks validated"} in validation.facts
    assert Enum.count(nodes, &(&1.status == :complete)) == 1
  end

  test "the ceiling is stated in calls and tokens, never in money" do
    Importer.import!(CatalogFixture.root())

    for node <- graph(), {"Run ceiling", value} <- node.facts do
      assert value == "44 model calls · 900000 input tokens · 16000 output tokens"
    end
  end

  defp graph do
    Query.list_climbs()
    |> List.first()
    |> EvidenceGraph.from_climb(ReleaseInfo.current())
  end
end
