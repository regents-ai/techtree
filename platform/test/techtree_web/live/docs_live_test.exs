defmodule TechtreeWeb.DocsLiveTest do
  use TechtreeWeb.ConnCase, async: false

  import Phoenix.LiveViewTest

  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture

  @section_ids ~w(
    install first-climb hermes verify publish integration data-boundary troubleshooting
    method proof-bundle trust-boundary hello-world beyond-model environments agent-stack regents
    research-start
  )

  setup do
    CatalogFixture.use_bundle(CatalogFixture.root())
    Importer.import!(CatalogFixture.root())
    :ok
  end

  test "the operator reference and its complete table of contents render", %{conn: conn} do
    {:ok, live, html} = live(conn, ~p"/docs")
    text = visible_text(html)

    assert text =~ "Operation Guide and Mechanism Docs"
    assert text =~ "Install the released CLI"
    assert text =~ "run your first A/B eval"
    assert text =~ "publish it to our public dashboard"

    assert text =~
             "For the info on Prime Intellect’s verifiers mechanism, go to the section Method."

    assert text =~ "Use the machine interface"
    assert text =~ "Troubleshoot from the boundary inward"
    assert text =~ "Most agent improvements are anecdotes."
    assert text =~ "Did changing this one Skill make the agent better?"

    assert has_element?(live, ".docs-nav__group > p", "CLI")
    assert has_element?(live, ".docs-nav__group > p", "Method")
    refute has_element?(live, ".docs-nav__group > p", "Integrate")
    refute has_element?(live, ".docs-nav__group > p", "Research")

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
    assert has_element?(live, ~s|a[href="#method"]|, "Method.")
    assert has_element?(live, ~s|a[href="/proofs"]|)
    assert has_element?(live, ~s|a[href="/results"]|, "Results")
  end

  test "the research method, trust boundary, and roadmap follow the operator reference", %{
    conn: conn
  } do
    {:ok, _live, html} = live(conn, ~p"/docs")
    text = visible_text(html)

    assert text =~ "The proof is participant-attested"
    assert text =~ "Techtree witnessed the run;"
    assert text =~ "another party reproduced it;"
    assert text =~ "Environments in v0.2"
    assert text =~ "NVIDIA NeMo Fabric"
    assert text =~ "Techtree is the research and proof engine"
    assert text =~ "x402-gated services"

    assert html =~ ~r/id="troubleshooting".*id="method"/s
  end

  test "research references and product destinations remain linked", %{conn: conn} do
    {:ok, live, html} = live(conn, ~p"/docs")

    for href <- [
          "https://github.com/PrimeIntellect-ai/verifiers",
          "https://github.com/NousResearch/hermes-agent",
          "https://github.com/regents-ai/techtree",
          "https://github.com/NVIDIA/NeMo-Fabric",
          "https://github.com/NVIDIA/NeMo-Relay",
          "/start",
          "/results"
        ] do
      assert has_element?(live, ~s|a[href="#{href}"]|)
    end

    refute html =~ "utm_source"
  end

  test "the page copies the complete combined article as Markdown", %{conn: conn} do
    {:ok, live, html} = live(conn, ~p"/docs")

    assert html =~ ~s|phx-hook="CopyCommandPage"|
    assert html =~ ~s|phx-hook="CopyCommandPageView"|
    assert html =~ "Copy page as Markdown for agents"
    assert html =~ "View as Markdown"

    assert has_element?(live, "article.docs-content[data-markdown-root] #install")
    assert has_element?(live, "article.docs-content[data-markdown-root] #method")
    assert has_element?(live, "article.docs-content[data-markdown-root] #research-start")

    app_js = File.read!("assets/js/app.js")
    assert app_js =~ ~s|document.querySelector("[data-markdown-root]")|
    assert app_js =~ "new URL(href, window.location.href).href"
  end
end
