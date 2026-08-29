defmodule TechtreeWeb.DocsLiveTest do
  use TechtreeWeb.ConnCase, async: true

  import Phoenix.LiveViewTest

  @section_ids ~w(
    question comparison proof-bundle trust-boundary hello-world beyond-model
    environments agent-stack regents start verifier-checks
  )

  test "the replacement article and its complete table of contents render", %{conn: conn} do
    {:ok, live, html} = live(conn, ~p"/docs")
    text = visible_text(html)

    assert text =~ "Most agent improvements are anecdotes."
    assert text =~ "Did changing this one Skill make the agent better?"
    assert text =~ "The offline verifier currently performs 17 checks"

    for id <- @section_ids do
      assert has_element?(live, ~s|##{id}|)
      assert has_element?(live, ~s|.docs-nav a[href="##{id}"]|)
    end
  end

  test "the supplied trust boundary and roadmap are preserved", %{conn: conn} do
    {:ok, _live, html} = live(conn, ~p"/docs")
    text = visible_text(html)

    assert text =~ "The proof is participant-attested"
    assert text =~ "Techtree witnessed the run;"
    assert text =~ "another party reproduced it;"
    assert text =~ "Environments in v0.2"
    assert text =~ "NVIDIA NeMo Fabric"
    assert text =~ "Techtree is the research and proof engine"
    assert text =~ "x402-gated services"
  end

  test "the external references and setup destinations are linked", %{conn: conn} do
    {:ok, live, _html} = live(conn, ~p"/docs")

    for href <- [
          "https://github.com/PrimeIntellect-ai/verifiers?utm_source=chatgpt.com",
          "https://github.com/NousResearch/hermes-agent",
          "https://github.com/regents-ai/techtree",
          "https://github.com/NVIDIA/NeMo-Fabric?utm_source=chatgpt.com",
          "https://github.com/NVIDIA/NeMo-Relay?utm_source=chatgpt.com",
          "https://techtree.sh/start",
          "https://techtree.sh/results"
        ] do
      assert has_element?(live, ~s|a[href="#{href}"]|)
    end
  end

  test "the old operating manual is fully absent", %{conn: conn} do
    {:ok, _live, html} = live(conn, ~p"/docs")
    text = visible_text(html)

    for stale <- [
          "Operate and integrate Techtree.",
          "What leaves my machine?",
          "Command reference",
          "Configuration and environment variables",
          "Release integrity",
          "Troubleshooting",
          "Experimental guided revision"
        ] do
      refute text =~ stale
    end
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

  test "the page still offers itself as Markdown", %{conn: conn} do
    {:ok, _live, html} = live(conn, ~p"/docs")

    assert html =~ ~s|phx-hook="CopyCommandPage"|
    assert html =~ ~s|phx-hook="CopyCommandPageView"|
    assert html =~ "Copy page as Markdown for agents"
    assert html =~ "View as Markdown"
  end
end
