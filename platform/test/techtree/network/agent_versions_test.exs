defmodule Techtree.Network.AgentVersionsTest do
  use Techtree.DataCase, async: false

  alias Techtree.Network.{AgentVersions, Query}
  alias Techtree.NetworkFixture
  alias Techtree.Catalog.Digest

  test "discovery is independent of keyset pages and version precedence is not upload order" do
    seed(1, "hermes-agent", "0.21.0")
    for sequence <- 2..30, do: seed(sequence, "hermes-agent", "0.9.0")
    seed(31, "codex", "0.100.0")
    seed(32, "codex", "0.99.0")
    seed(33, "hermes-agent", "0.21.0-rc.1")

    families = Query.agent_families()
    assert [hermes, codex] = families
    assert hermes.versions == ["0.21.0", "0.21.0-rc.1", "0.9.0"]
    assert codex.versions == ["0.100.0", "0.99.0"]
    assert {:ok, %{version: "0.21.0"}} = AgentVersions.select(families, %{})

    page = Query.page(agent: "hermes-agent", agent_version: "0.9.0", limit: 2)
    assert Enum.map(page.entries, & &1.log_sequence) == [30, 29]
    assert page.next_before_sequence == 29

    next =
      Query.page(agent: "hermes-agent", agent_version: "0.9.0", before_sequence: 29, limit: 2)

    assert Enum.map(next.entries, & &1.log_sequence) == [28, 27]
    assert Enum.all?(next.entries, &(&1.subject_harness_version == "0.9.0"))

    assert {:error, _} =
             AgentVersions.select(families, %{"agent" => "codex", "agent_version" => "0.21.0"})
  end

  test "opaque identifiers stay exact and duplicate uploads do not reorder known builds" do
    seed(1, "codex", "build/alpha+sha")
    seed(2, "codex", "build/beta+sha")
    seed(3, "codex", "build/alpha+sha")
    assert [%{versions: ["build/beta+sha", "build/alpha+sha"]}] = Query.agent_families()

    url = AgentVersions.url("codex", "build/alpha+sha", before_sequence: 9)

    assert URI.decode_query(URI.parse(url).query) == %{
             "agent" => "codex",
             "agent_version" => "build/alpha+sha",
             "before_sequence" => "9"
           }
  end

  test "HTTP selection rejects scalar coercions and half-specified coordinates" do
    for params <- [
          %{"agent" => "hermes-agent"},
          %{"agent" => [], "agent_version" => "0.21.0"},
          %{"agent" => "hermes-agent", "agent_version" => false}
        ] do
      assert {:error, _} = Query.read_page_options(params)
    end
  end

  defp seed(sequence, agent, version) do
    NetworkFixture.seed_entry(
      log_sequence: sequence,
      bundle_digest: Digest.hash_bytes("version-query-#{sequence}"),
      run_id: "version-query-#{sequence}",
      subject_harness: agent,
      subject_harness_version: version
    )
  end
end
