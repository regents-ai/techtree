defmodule TechtreeWeb.ClimbsLiveTest do
  use TechtreeWeb.ConnCase, async: false

  import Phoenix.LiveViewTest

  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture

  describe "the list, with a release being served" do
    setup do
      CatalogFixture.use_bundle(CatalogFixture.root())
      Importer.import!(CatalogFixture.root())
      :ok
    end

    test "each Climb is described by what it measures and what it asks", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/climbs")
      text = visible_text(html)

      assert text =~ "Techtree Hello World"
      assert text =~ "In development"
      assert text =~ "Does one added component make the agent better?"
      assert text =~ "One skill is added. Nothing else may differ."
      assert text =~ "Tasks 36"
      refute text =~ "BranchCode"
      assert text =~ "hermes-agent 0.19.0"
      assert text =~ "hello-world-climb@1"
    end

    test "the card carries the names this Climb is published under", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/climbs")
      text = visible_text(html)

      assert text =~ "Techtree Hello World"
      assert text =~ "A toy Skill-uplift Climb"
      assert text =~ "Hello World Skill Uplift"
      refute text =~ "BranchCode"
    end

    test "the card says this is a toy demonstration rather than a benchmark", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/climbs")
      text = visible_text(html)

      assert text =~ "introductory demonstration of the mechanism"
      assert text =~ "not a measure of broad capability"
      refute text =~ "HelloWorldBench"
    end

    test "the rights a participant would accept are on the list page", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/climbs")
      text = visible_text(html)

      assert text =~ "Stay on your machine. They are never uploaded."
      assert text =~ "never used to train a model"
      assert text =~ "published as part of entering"
    end

    test "a development Climb does not pass itself off as evidence", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/climbs")

      assert visible_text(html) =~ "not evidence of anything"
    end

    test "no ranking of any kind is shown", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/climbs")
      text = html |> visible_text() |> String.downcase()

      for ranked <- ["leaderboard", "rank", "top score", "best result"] do
        refute text =~ ranked
      end
    end

    test "a Climb links to its own page", %{conn: conn} do
      {:ok, live, _html} = live(conn, ~p"/climbs")

      assert live |> element(~s|a[href="/climbs/hello-world-climb"]|) |> has_element?()
    end
  end

  describe "the list, with nothing imported" do
    setup do
      CatalogFixture.use_bundle(CatalogFixture.root())
    end

    test "says so, and says it does not block a trial", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/climbs")
      text = visible_text(html)

      assert text =~ "No Climbs are published on this site at the moment"
      assert text =~ "does not stop a Test on your own machine"
    end
  end

  describe "one Climb" do
    setup do
      CatalogFixture.use_bundle(CatalogFixture.root())
      Importer.import!(CatalogFixture.root())
      :ok
    end

    test "keeps the invitation and the trial apart", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/climbs/hello-world-climb")
      text = visible_text(html)

      assert text =~ "The invitation"
      assert text =~ "The Test"
      assert text =~ "ClimbManifest"
      assert text =~ "CampaignSpec"
    end

    test "shows what is measured and what is held fixed", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/climbs/hello-world-climb")
      text = visible_text(html)

      assert text =~ "Tasks 36"
      refute text =~ "BranchCode"
      assert text =~ "One skill is added. Nothing else may differ."
      assert text =~ "exact match"
      assert text =~ "Side by side, started together on one machine."
      assert text =~ "docker container with 2 cores and 4 GB of memory"
      assert text =~ "network restricted"
    end

    test "carries the public names and references of the fixed contract", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/climbs/hello-world-climb")
      text = visible_text(html)

      assert text =~ "Techtree Hello World"
      assert text =~ "A toy Skill-uplift Climb"
      assert text =~ "Hello World Skill Uplift"
      assert text =~ "hello-world-climb@1"
      assert text =~ "hello-world-starter-v1"
      refute text =~ "BranchCode"
      refute text =~ "Hello World Uplift Receipt"
      refute text =~ "Hello World — Iteration 2"
      refute text =~ "HelloWorldBench"
    end

    test "discloses that the starter Skill is deliberately incomplete", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/climbs/hello-world-climb")

      assert visible_text(html) =~
               "The Hello World starter Skill is intentionally incomplete and calibrated " <>
                 "to solve roughly two-thirds of the toy tasks. Individual runs may vary. " <>
                 "The gap is deliberate, so that the guided one-turn revision has " <>
                 "measurable headroom."
    end

    test "says this is a toy demonstration rather than a benchmark", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/climbs/hello-world-climb")
      text = visible_text(html)

      assert text =~ "introductory demonstration of the mechanism"
      assert text =~ "not a measure of broad capability"
    end

    test "shows the rights without reteaching the proof boundary", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/climbs/hello-world-climb")
      text = visible_text(html)

      assert text =~ "Stay on your machine. They are never uploaded."
      refute text =~ "this site does not watch it happen"
      refute text =~ "What a result may be called"
    end

    test "links every document by its fingerprint", %{conn: conn} do
      {:ok, live, html} = live(conn, ~p"/climbs/hello-world-climb")

      for digest <- [
            CatalogFixture.climb_digest(),
            CatalogFixture.campaign_digest()
          ] do
        assert html =~ digest
        assert live |> element(~s|a[href="/api/v1/objects/#{digest}"]|) |> has_element?()
      end
    end

    test "the contract sends the first-run walkthrough to Start", %{conn: conn} do
      {:ok, live, html} = live(conn, ~p"/climbs/hello-world-climb")
      text = visible_text(html)

      assert has_element?(live, ~s|a[href="/start"]|, "Start")
      assert text =~ "This page remains the fixed Test contract."
      refute text =~ "techtree climb prepare"
    end

    test "a slug that names nothing is not found", %{conn: conn} do
      assert_error_sent 404, fn -> live(conn, ~p"/climbs/no-such-climb") end
    end

    test "a slug is never treated as a path", %{conn: conn} do
      assert_error_sent 404, fn -> live(conn, "/climbs/..%2F..%2Fetc%2Fpasswd") end
    end
  end
end
