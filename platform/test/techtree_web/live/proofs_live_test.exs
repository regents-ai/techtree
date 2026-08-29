defmodule TechtreeWeb.ProofsLiveTest do
  @moduledoc """
  Proofs shows one complete certification Result, its evidence coordinates,
  and the boundary of participant attestation.
  """

  use TechtreeWeb.ConnCase, async: false

  import Phoenix.LiveViewTest

  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture

  describe "with a release published" do
    setup do
      CatalogFixture.use_bundle(CatalogFixture.root())
      Importer.import!(CatalogFixture.root())
      :ok
    end

    test "shows the certified example from the served report", %{conn: conn} do
      {:ok, live, html} = live(conn, ~p"/proofs")
      text = visible_text(html)
      example = TechtreeWeb.ExampleResult.load()

      assert example, "the example report is missing from priv/examples"
      assert text =~ "What verification establishes"
      assert text =~ "Example Baseline vs. Instructional Skill"
      assert text =~ "#{example.baseline_total} of #{example.tasks} tasks"
      assert text =~ "#{example.candidate_total} of #{example.tasks} tasks"
      assert text =~ "#{example.wins} wins · #{example.ties} ties · #{example.losses} losses"
      assert text =~ example.file_digest
      assert text =~ example.run_id
      assert text =~ "Nobody outside this project has reproduced it."
      assert text =~ "Verification is not observation."
      assert text =~ "does not prove the machine behaved honestly"
      assert has_element?(live, ~s|a[href="/results"]|, "Browse published Results.")
    end

    test "shows the full evidence graph and fixed comparison", %{conn: conn} do
      {:ok, live, html} = live(conn, ~p"/proofs")
      text = visible_text(html)

      assert has_element?(live, "#proof-evidence-graph")
      assert text =~ CatalogFixture.campaign_digest()
      assert text =~ "36 tasks, fixed before either Test"
      assert text =~ "hermes-agent 0.19.0"
      assert text =~ "prime · qwen/qwen3.7-flash"
      assert text =~ "44 model calls"
      assert text =~ "One Skill, mounted in the candidate and absent from the baseline."
      assert text =~ Techtree.Release.StarterSkill.tree_digest()

      assert has_element?(
               live,
               ~s|a[href="/climbs/hello-world-climb"]|,
               "Hello World Skill Uplift"
             )

      refute html =~ ~s|href="/runs"|
      refute html =~ ~s|href="/campaigns/|
    end

    test "the reader can verify a bundle offline", %{conn: conn} do
      {:ok, live, html} = live(conn, ~p"/proofs")

      assert visible_text(html) =~
               "Only a run carries those. The bundle is signed on the machine that produced it, and anyone holding a copy can check it on their own machine, offline."

      assert live
             |> element(
               ~s|#copy-proof-verify[data-copy-value="techtree proof verify path/to/result-bundle"]|
             )
             |> has_element?()
    end
  end

  test "without a catalog the page explains what is unavailable", %{conn: conn} do
    CatalogFixture.use_bundle(CatalogFixture.root())

    {:ok, _live, html} = live(conn, ~p"/proofs")
    text = visible_text(html)

    assert text =~ "No Climb is published on this channel"
    assert text =~ "No certification Result is available on this channel"
    assert text =~ "Published comparisons appear in Results"
  end
end
