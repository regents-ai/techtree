defmodule TechtreeWeb.CampaignsLiveTest do
  @moduledoc """
  The campaign pages are the coordinates and nothing else: what was fixed,
  where each fixed thing is written down, and what the terms would mean. A
  result would need a run, and there has not been one.
  """

  use TechtreeWeb.ConnCase, async: false

  import Phoenix.LiveViewTest

  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture
  alias Techtree.Release.StarterSkill

  setup do
    CatalogFixture.use_bundle(CatalogFixture.root())
    :ok
  end

  test "the index comes only from the imported catalog", %{conn: conn} do
    Importer.import!(CatalogFixture.root())
    {:ok, live, html} = live(conn, ~p"/campaigns")
    text = visible_text(html)

    assert text =~ "Hello World Skill Uplift"
    assert text =~ "36 tasks, fixed before either run"
    assert text =~ "hermes-agent 0.19.0"
    assert text =~ "prime · qwen/qwen3.7-flash"

    assert live
           |> element(~s|a[href="/campaigns/hello-world-climb"]|, "Inspect campaign")
           |> has_element?()
  end

  test "the detail page shows the fixed coordinates and the graph", %{conn: conn} do
    Importer.import!(CatalogFixture.root())
    {:ok, live, html} = live(conn, ~p"/campaigns/hello-world-climb")
    text = visible_text(html)

    assert has_element?(live, "#campaign-evidence-graph")
    assert text =~ CatalogFixture.campaign_digest()
    assert text =~ "prime · qwen/qwen3.7-flash"
    assert text =~ "44 model calls"
    assert text =~ "A docker container, 2 cores, 4 GB"
    assert text =~ "No Skill in the baseline branch"
    assert text =~ "The candidate Skill is recorded when a participant prepares the run."

    assert live
           |> element("#campaign-starter-skill")
           |> has_element?()

    assert live
           |> element("a[href=\"/api/v1/objects/#{StarterSkill.file_digest()}\"]")
           |> has_element?()

    # Nothing here is a result, and no figure is invented for one.
    refute text =~ ~r/\+?\d+(\.\d+)?\s*%/
  end

  test "the terms are never shown without what this release does with them", %{conn: conn} do
    Importer.import!(CatalogFixture.root())
    {:ok, _live, html} = live(conn, ~p"/campaigns/hello-world-climb")
    text = visible_text(html)

    assert text =~ "Would be published as part of entering"

    assert text =~
             "Nothing you produce is published unless you publish a finished run yourself."

    assert text =~
             "the complete proof bundle"
  end

  test "what a run may spend is stated in calls and tokens, never in money", %{conn: conn} do
    Importer.import!(CatalogFixture.root())
    {:ok, _live, html} = live(conn, ~p"/campaigns/hello-world-climb")
    text = visible_text(html)

    assert text =~ "44 model calls · 900000 input tokens · 16000 output tokens"
    refute text =~ "2.5"
    assert text =~ "What the calls themselves cost is set by your model provider"
  end

  test "every coordinate on the detail page links to the document it came from",
       %{conn: conn} do
    Importer.import!(CatalogFixture.root())
    {:ok, live, _html} = live(conn, ~p"/campaigns/hello-world-climb")

    for {digest, label} <- [
          {CatalogFixture.campaign_digest(), "Campaign definition"},
          {CatalogFixture.taskset_validation_digest(), "Task validation"},
          {CatalogFixture.data_policy_digest(), "Data policy"}
        ] do
      assert live
             |> element(~s|a[href="/api/v1/objects/#{digest}"]|, label)
             |> has_element?()
    end
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
