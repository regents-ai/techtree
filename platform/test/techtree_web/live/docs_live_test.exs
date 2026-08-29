defmodule TechtreeWeb.DocsLiveTest do
  use TechtreeWeb.ConnCase, async: false

  import Phoenix.LiveViewTest

  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture

  @section_ids ~w(
    install first-climb hermes verify publish integration data-boundary troubleshooting
    research comparison proof-bundle trust-boundary hello-world beyond-model environments
    agent-stack regents research-start verifier-checks
  )

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
    assert text =~ "Most agent improvements are anecdotes."
    assert text =~ "Did changing this one Skill make the agent better?"
    assert text =~ "The offline verifier currently performs 17 checks"

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
    assert has_element?(live, ~s|a[href="#research"]|, "Research")
    assert has_element?(live, ~s|a[href="/proofs"]|, "Verify")
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

    assert html =~ ~r/id="troubleshooting".*id="research"/s
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

  test "all 17 verifier checks render", %{conn: conn} do
    {:ok, live, _html} = live(conn, ~p"/docs")

    [list_html] =
      Regex.run(
        ~r/<section id="verifier-checks".*?<ol.*?>(.*?)<\/ol>/s,
        render(live),
        capture: :all_but_first
      )

    assert length(Regex.scan(~r/<li>/, list_html)) == 17
  end

  test "the page offers itself as Markdown", %{conn: conn} do
    {:ok, _live, html} = live(conn, ~p"/docs")

    assert html =~ ~s|phx-hook="CopyCommandPage"|
    assert html =~ ~s|phx-hook="CopyCommandPageView"|
    assert html =~ "Copy page as Markdown for agents"
    assert html =~ "View as Markdown"
  end
end
