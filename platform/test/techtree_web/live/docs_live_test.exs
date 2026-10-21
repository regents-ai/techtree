defmodule TechtreeWeb.DocsLiveTest do
  use TechtreeWeb.ConnCase, async: false

  import Phoenix.LiveViewTest

  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture
  alias TechtreeWeb.DocsGuides

  setup do
    CatalogFixture.use_bundle(CatalogFixture.root())
    Importer.import!(CatalogFixture.root())
    :ok
  end

  test "the Docs page links every guide, by group", %{conn: conn} do
    {:ok, live, _html} = live(conn, ~p"/docs")

    for {group, guides} <- DocsGuides.groups() do
      assert has_element?(live, ".docs-index__group h2", group)

      for guide <- guides do
        assert has_element?(live, ~s|a[href="/docs/#{guide.slug}"]|, guide.title)
      end
    end
  end

  test "every guide opens on its own page, marked in the menu", %{conn: conn} do
    for guide <- DocsGuides.all() do
      {:ok, live, _html} = live(conn, ~p"/docs/#{guide.slug}")

      assert has_element?(live, "article.docs-content[data-markdown-root] h1")

      assert has_element?(
               live,
               ~s|.docs-nav a[href="/docs/#{guide.slug}"][aria-current="page"]|
             )

      assert page_title(live) =~ guide.title
    end
  end

  test "next and previous follow the reading order", %{conn: conn} do
    [first, second | _rest] = DocsGuides.all()
    last = List.last(DocsGuides.all())

    {:ok, live, _html} = live(conn, ~p"/docs/#{first.slug}")
    assert has_element?(live, ~s|.docs-pager a[href="/docs/#{second.slug}"]|)
    assert live |> element(".docs-pager a") |> render() =~ "Next"

    {:ok, live, _html} = live(conn, ~p"/docs/#{last.slug}")
    assert live |> element(".docs-pager a") |> render() =~ "Previous"
  end

  test "an unknown guide is a missing page", %{conn: conn} do
    assert_error_sent 404, fn -> get(conn, "/docs/no-such-guide") end
  end

  @tag :tmp_dir
  test "the guides with commands render them from the release", %{
    conn: conn,
    tmp_dir: tmp_dir
  } do
    bundle = CatalogFixture.copy!(tmp_dir)
    CatalogFixture.rewrite_bootstrap!(bundle, &CatalogFixture.concrete_release/1)
    CatalogFixture.use_bundle(bundle)
    Importer.import!(bundle)

    {:ok, _live, html} = live(conn, ~p"/docs/install")
    assert visible_text(html) =~ "regents techtree doctor --climb"

    {:ok, _live, html} = live(conn, ~p"/docs/test-a-skill")
    text = visible_text(html)
    assert text =~ "regents techtree forge compare BASELINE_RUN_ID CANDIDATE_RUN_ID"
    assert text =~ "--skill path/to/earlier-skill"

    {:ok, _live, html} = live(conn, ~p"/docs/hello-world")
    assert visible_text(html) =~ "regents techtree climb prepare"

    {:ok, live, html} = live(conn, ~p"/docs/hermes")
    assert copied_text(html, "copy-docs-hermes") =~ "agents.md"
    assert has_element?(live, "#copy-docs-hermes-plugin")

    {:ok, _live, html} = live(conn, ~p"/docs/verify")
    assert visible_text(html) =~ "regents techtree proof verify path/to/result-bundle"

    {:ok, _live, html} = live(conn, ~p"/docs/publish")
    text = visible_text(html)
    assert text =~ "regents techtree publish RUN_ID"
    assert text =~ "regents techtree withdraw BUNDLE_DIGEST"
  end

  test "a guide page and its Markdown say the same thing", %{conn: conn} do
    {:ok, _live, html} = live(conn, ~p"/docs/api")
    markdown = conn |> put_req_header("accept", "text/markdown") |> get("/docs/api")

    assert visible_text(html) =~ "GET /api/v1/bootstrap"
    assert response(markdown, 200) =~ "GET /api/v1/bootstrap"
  end

  test "each page copies its own article as Markdown", %{conn: conn} do
    {:ok, live, html} = live(conn, ~p"/docs/method")

    assert html =~ ~s|phx-hook="CopyCommandPage"|
    assert has_element?(live, "#copy-page + [data-copy-status][role=status][aria-atomic=true]")
    refute has_element?(live, "[data-markdown-root] .docs-nav")
    assert has_element?(live, "[data-markdown-root] .docs-pager[data-markdown-skip]")

    app_js = File.read!("assets/js/app.ts")
    assert app_js =~ ~s|document.querySelector("[data-markdown-root]")|
  end
end
