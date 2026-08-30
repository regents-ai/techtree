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
  alias Techtree.Network.Query, as: NetworkQuery
  alias Techtree.NetworkFixture
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

    assert Enum.map(nodes, & &1.id) == [
             "campaign",
             "validation",
             "baseline",
             "candidate",
             "proofs"
           ]

    for node <- nodes, node.digest do
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
      assert {"Status", "Declared branch"} in node.facts
    end

    for node <- nodes, {_term, value} <- node.facts do
      refute value =~ ~r/\b\d{1,3}\s*(\/|out of)\s*36\b/
      refute value =~ ~r/\b\d{1,3}\s*%/
    end

    refute Enum.any?(nodes, fn node ->
             node.id == "candidate" and
               Enum.any?(node.facts, fn {term, _value} -> term == "Score band" end)
           end)

    assert {"Status", "No published proofs yet"} in Enum.find(nodes, &(&1.id == "proofs")).facts
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

    for node <- graph(), {"Per-branch ceiling", value} <- node.facts do
      assert value == "44 model calls · 900000 input tokens · 16000 output tokens"
    end
  end

  test "published proof links stay truthful for one or many receipts" do
    Importer.import!(CatalogFixture.root())
    climb = Query.list_climbs() |> List.first()

    proofs = [
      proof("sha256:" <> String.duplicate("a", 64), 24, 12, 0),
      proof("sha256:" <> String.duplicate("b", 64), 22, 14, 0)
    ]

    node =
      EvidenceGraph.from_climb(climb, ReleaseInfo.current(), proofs)
      |> Enum.find(&(&1.id == "proofs"))

    assert node.status == :published
    assert {"Status", "2 recorded proofs"} in node.facts

    assert node.links == [
             {"24 better · 12 same · 0 worse", "/results/sha256:" <> String.duplicate("a", 64)},
             {"22 better · 14 same · 0 worse", "/results/sha256:" <> String.duplicate("b", 64)}
           ]
  end

  test "withdrawn receipts are visible but not counted as active" do
    Importer.import!(CatalogFixture.root())
    climb = Query.list_climbs() |> List.first()

    withdrawn =
      proof("sha256:" <> String.duplicate("c", 64), 20, 16, 0)
      |> Map.put(:withdrawn_at, DateTime.utc_now())

    node = EvidenceGraph.from_climb(climb, ReleaseInfo.current(), [withdrawn]) |> List.last()

    assert node.status == :published
    assert {"Status", "1 recorded proof · 1 withdrawn"} in node.facts

    assert node.links == [
             {"Withdrawn · 20 better · 16 same · 0 worse", "/results/" <> withdrawn.bundle_digest}
           ]
  end

  test "a capped proof sample does not invent a total" do
    Importer.import!(CatalogFixture.root())
    climb = Query.list_climbs() |> List.first()

    proofs =
      for number <- 1..12 do
        proof("sha256:" <> String.pad_leading(Integer.to_string(number), 64, "0"), 24, 12, 0)
      end

    node =
      EvidenceGraph.from_climb(
        climb,
        ReleaseInfo.current(),
        %{entries: proofs, truncated?: true}
      )
      |> List.last()

    assert {"Status", "Showing 12 most recent proofs"} in node.facts
  end

  test "the campaign proof query returns only the fields the graph displays" do
    Importer.import!(CatalogFixture.root())
    assert {:ok, _entry, :recorded} = NetworkFixture.publish()

    %{entries: [proof], truncated?: false} =
      NetworkQuery.for_campaign(CatalogFixture.campaign_digest())

    assert proof.bundle_digest == NetworkFixture.bundle_digest()
    assert proof.wins == 23
    assert proof.ties == 13
    assert proof.losses == 0
    assert proof.task_count == 36

    graph_proofs =
      Query.list_climbs()
      |> List.first()
      |> EvidenceGraph.from_climb(
        ReleaseInfo.current(),
        NetworkQuery.for_campaign(CatalogFixture.campaign_digest())
      )
      |> Enum.find(&(&1.id == "proofs"))

    assert graph_proofs.status == :published

    assert graph_proofs.links == [
             {"23 better · 13 same · 0 worse", "/results/" <> proof.bundle_digest}
           ]
  end

  defp graph do
    Query.list_climbs()
    |> List.first()
    |> EvidenceGraph.from_climb(ReleaseInfo.current())
  end

  defp proof(bundle_digest, wins, ties, losses) do
    %{bundle_digest: bundle_digest, wins: wins, ties: ties, losses: losses}
  end
end
