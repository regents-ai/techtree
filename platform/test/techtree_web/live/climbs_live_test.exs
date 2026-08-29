defmodule TechtreeWeb.ClimbsLiveTest do
  use TechtreeWeb.ConnCase, async: false

  import Phoenix.LiveViewTest

  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture

  describe "one Climb" do
    setup do
      CatalogFixture.use_bundle(CatalogFixture.root())
      Importer.import!(CatalogFixture.root())
      :ok
    end

    test "shows a concise test contract without repeating setup", %{conn: conn} do
      {:ok, live, html} = live(conn, ~p"/climbs/hello-world-climb")
      text = visible_text(html)

      assert text =~ "Techtree Hello World"
      assert text =~ "Does adding the Hello World Skill improve exact-match scores"
      assert text =~ "One skill is added. Nothing else may differ."
      assert text =~ "Tasks 36, fixed before either Run"
      assert text =~ "model, Hermes harness, runtime, tools, sampling, and budget"
      assert text =~ "Expected output"
      assert text =~ "Scoring"
      refute text =~ "Set up Techtree and run the Hello World Climb."
      refute has_element?(live, "#copy-climb-setup-instruction")

      refute text =~ "Two documents, two jobs"
      refute text =~ "What this asks of you"
      refute text =~ "Integrity details"
      refute text =~ "BranchCode"
      assert has_element?(live, ~s|a[href="/results"]|, "Browse Results from published Climbs")
    end

    test "a slug that names nothing is not found", %{conn: conn} do
      assert_error_sent 404, fn -> live(conn, ~p"/climbs/no-such-climb") end
    end

    test "a slug is never treated as a path", %{conn: conn} do
      assert_error_sent 404, fn -> live(conn, "/climbs/..%2F..%2Fetc%2Fpasswd") end
    end
  end

  describe "with nothing imported" do
    setup do
      CatalogFixture.use_bundle(CatalogFixture.root())
    end

    test "a Climb page is not found rather than empty", %{conn: conn} do
      assert_error_sent 404, fn -> live(conn, ~p"/climbs/hello-world-climb") end
    end
  end
end
