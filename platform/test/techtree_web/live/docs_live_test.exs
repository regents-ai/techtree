defmodule TechtreeWeb.DocsLiveTest do
  use TechtreeWeb.ConnCase, async: false

  import Phoenix.LiveViewTest

  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture

  @section_ids ~w(install first-climb hermes verify publish integration data-boundary troubleshooting)

  setup do
    CatalogFixture.use_bundle(CatalogFixture.root())
    Importer.import!(CatalogFixture.root())
    :ok
  end

  test "the operator reference and its complete table of contents render", %{conn: conn} do
    {:ok, live, html} = live(conn, ~p"/docs")
    text = visible_text(html)

    assert text =~ "Operate and integrate Techtree."
    assert text =~ "Install the released CLI"
    assert text =~ "Use the machine interface"
    assert text =~ "Troubleshoot from the boundary inward"

    for id <- @section_ids do
      assert has_element?(live, ~s|##{id}|)
      assert has_element?(live, ~s|.docs-nav a[href="##{id}"]|)
    end
  end

  @tag :tmp_dir
  test "commands, API endpoints, and supporting routes are explicit", %{
    conn: conn,
    tmp_dir: tmp_dir
  } do
    bundle = CatalogFixture.copy!(tmp_dir)
    CatalogFixture.rewrite_bootstrap!(bundle, &CatalogFixture.concrete_release/1)
    CatalogFixture.use_bundle(bundle)
    Importer.import!(bundle)

    {:ok, live, html} = live(conn, ~p"/docs")
    text = visible_text(html)

    assert text =~ "techtree doctor --climb"
    assert text =~ "techtree climb prepare"
    assert text =~ "techtree proof verify path/to/result-bundle"
    assert text =~ "techtree publish RUN_ID"
    assert text =~ "GET /api/v1/bootstrap"
    assert text =~ "GET /api/v1/publications/:digest"
    assert has_element?(live, ~s|a[href="/research"]|, "Research")
    assert has_element?(live, ~s|a[href="/proofs"]|, "Verify")
    assert has_element?(live, ~s|a[href="/results"]|, "Results")
  end

  test "research teaching stays on the research route", %{conn: conn} do
    {:ok, _live, html} = live(conn, ~p"/docs")
    text = visible_text(html)

    refute text =~ "Most agent improvements are anecdotes."
    refute text =~ "Environments in v0.2"
    refute text =~ "The 17 verifier checks"
  end

  test "the page offers itself as Markdown", %{conn: conn} do
    {:ok, _live, html} = live(conn, ~p"/docs")

    assert html =~ ~s|phx-hook="CopyCommandPage"|
    assert html =~ ~s|phx-hook="CopyCommandPageView"|
    assert html =~ "Copy page as Markdown for agents"
    assert html =~ "View as Markdown"
  end
end
