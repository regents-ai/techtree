defmodule TechtreeWeb.ClimbsLiveTest do
  use TechtreeWeb.ConnCase, async: false

  import Phoenix.LiveViewTest

  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture

  @instruction "Set up Techtree and run the Hello World Climb."

  describe "one Climb" do
    setup do
      CatalogFixture.use_bundle(CatalogFixture.root())
      Importer.import!(CatalogFixture.root())
      :ok
    end

    test "shows a concise test contract and one setup instruction", %{conn: conn} do
      {:ok, live, html} = live(conn, ~p"/climbs/hello-world-climb")
      text = visible_text(html)

      assert text =~ "Techtree Hello World"
      assert text =~ "Does one added component make the agent better?"
      assert text =~ "One skill is added. Nothing else may differ."
      assert text =~ "Tasks 36"
      assert text =~ "hermes-agent 0.19.0"
      assert text =~ @instruction

      assert has_element?(
               live,
               ~s|#copy-climb-setup-instruction[data-copy-value="#{@instruction}"]|,
               "Copy"
             )

      refute text =~ "Two documents, two jobs"
      refute text =~ "What this asks of you"
      refute text =~ "Integrity details"
      refute text =~ "BranchCode"
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
