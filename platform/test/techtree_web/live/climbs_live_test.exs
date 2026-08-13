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

      assert text =~ "Procedure Transfer Development Climb"
      assert text =~ "In development"
      assert text =~ "Does one added component make the agent better?"
      assert text =~ "One skill is added. Nothing else may differ."
      assert text =~ "36 tasks from procedure-transfer-v1"
      assert text =~ "hermes-agent 0.19.0"
      assert text =~ "procedure-transfer-dev@1"
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

      assert live |> element(~s|a[href="/climbs/procedure-transfer-dev"]|) |> has_element?()
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
      assert text =~ "does not stop a trial on your own machine"
    end
  end

  describe "one Climb" do
    setup do
      CatalogFixture.use_bundle(CatalogFixture.root())
      Importer.import!(CatalogFixture.root())
      :ok
    end

    test "keeps the invitation and the trial apart", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/climbs/procedure-transfer-dev")
      text = visible_text(html)

      assert text =~ "The invitation"
      assert text =~ "The trial"
      assert text =~ "ClimbManifest"
      assert text =~ "CampaignSpec"
    end

    test "shows what is measured and what is held fixed", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/climbs/procedure-transfer-dev")
      text = visible_text(html)

      assert text =~ "36 tasks from procedure-transfer-v1"
      assert text =~ "One skill is added. Nothing else may differ."
      assert text =~ "exact match"
      assert text =~ "One after the other, on the same machine."
      assert text =~ "docker container with 2 cores and 4 GB of memory"
      assert text =~ "network restricted"
    end

    test "shows the rights and the limits of a local result", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/climbs/procedure-transfer-dev")
      text = visible_text(html)

      assert text =~ "Stay on your machine. They are never uploaded."
      assert text =~ "this site does not watch it happen"
      assert text =~ "not evidence of anything"
    end

    test "links every document by its fingerprint", %{conn: conn} do
      {:ok, live, html} = live(conn, ~p"/climbs/procedure-transfer-dev")

      for digest <- [
            CatalogFixture.climb_digest(),
            CatalogFixture.campaign_digest()
          ] do
        assert html =~ digest
        assert live |> element(~s|a[href="/api/v1/objects/#{digest}"]|) |> has_element?()
      end
    end

    test "the entry commands name this Climb exactly", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/climbs/procedure-transfer-dev")
      text = visible_text(html)

      assert text =~ "techtree climb show procedure-transfer-dev@1"
      assert text =~ "techtree climb prepare procedure-transfer-dev@1 --skill path/to/skill"
    end

    test "a slug that names nothing is not found", %{conn: conn} do
      assert_error_sent 404, fn -> live(conn, ~p"/climbs/no-such-climb") end
    end

    test "a slug is never treated as a path", %{conn: conn} do
      assert_error_sent 404, fn -> live(conn, "/climbs/..%2F..%2Fetc%2Fpasswd") end
    end
  end
end
