defmodule TechtreeWeb.CampaignsLiveTest do
  use TechtreeWeb.ConnCase, async: false

  import Phoenix.LiveViewTest

  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture

  setup do
    CatalogFixture.use_bundle(CatalogFixture.root())
    :ok
  end

  test "the campaign index comes only from the imported catalog", %{conn: conn} do
    Importer.import!(CatalogFixture.root())
    {:ok, live, html} = live(conn, ~p"/campaigns")
    text = visible_text(html)

    assert text =~ "Hello World Skill Uplift"
    assert text =~ "36"
    assert text =~ "hermes-agent 0.19.0"

    assert live
           |> element(~s|a[href="/campaigns/hello-world-climb"]|, "Inspect campaign")
           |> has_element?()
  end

  test "the campaign detail exposes fixed coordinates and shared evidence", %{conn: conn} do
    Importer.import!(CatalogFixture.root())
    {:ok, live, html} = live(conn, ~p"/campaigns/hello-world-climb")
    text = visible_text(html)

    assert has_element?(live, "#campaign-evidence-graph")
    assert text =~ CatalogFixture.campaign_digest()
    assert text =~ "prime · qwen/qwen3.7-flash"
    assert text =~ "44 model calls"
    assert text =~ "No Skill in the baseline branch"
    assert text =~ "The candidate Skill digest is recorded when a participant prepares the run."
    refute text =~ ~r/\+?\d+(\.\d+)?%/
  end

  test "an empty catalog produces an honest empty index", %{conn: conn} do
    {:ok, _live, html} = live(conn, ~p"/campaigns")

    assert visible_text(html) =~ "No campaign is published on this channel."
  end

  test "an unknown campaign is not a placeholder page", %{conn: conn} do
    Importer.import!(CatalogFixture.root())

    assert_error_sent 404, fn -> live(conn, ~p"/campaigns/not-published") end
  end
end
