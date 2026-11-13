defmodule TechtreeWeb.DocsLiveTest do
  use TechtreeWeb.ConnCase, async: false

  import Phoenix.LiveViewTest

  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture
  alias TechtreeWeb.DocsGuides
  alias TechtreeWeb.DocsLive
  alias TechtreeWeb.ReleaseInfo

  setup do
    CatalogFixture.use_bundle(CatalogFixture.root())
    Importer.import!(CatalogFixture.root())
    :ok
  end

  test "the Docs page links every guide, by group", %{conn: conn} do
    {:ok, live, _html} = live(conn, ~p"/docs")

    for {group, guides} <- DocsGuides.groups() do
      assert has_element?(live, ".docs-index .mk-section h2", group)

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
    {:ok, live, html} = live(conn, ~p"/docs/verify")

    assert html =~ ~s|phx-hook="CopyCommandPage"|
    assert has_element?(live, "#copy-page + [data-copy-status][role=status][aria-atomic=true]")
    refute has_element?(live, "[data-markdown-root] .docs-nav")
    assert has_element?(live, "[data-markdown-root] .docs-pager[data-markdown-skip]")

    app_js = File.read!("assets/js/app.ts")
    assert app_js =~ ~s|document.querySelector("[data-markdown-root]")|
  end

  describe "Run locally, with an installable release" do
    setup %{tmp_dir: tmp_dir} do
      bundle = CatalogFixture.copy!(tmp_dir)
      CatalogFixture.rewrite_bootstrap!(bundle, &CatalogFixture.concrete_release/1)
      CatalogFixture.use_bundle(bundle)
      Importer.import!(bundle)
      :ok
    end

    @tag :tmp_dir
    test "the agent prompt comes first, then the release-derived setup and example", %{
      conn: conn
    } do
      {:ok, live, html} = live(conn, ~p"/docs/run-locally")
      release = ReleaseInfo.current()
      instruction = DocsLive.instruction()

      assert instruction =~ url(~p"/agents.md")
      assert copied_text(html, "copy-run-instruction") == instruction

      assert copied_text(html, "copy-run-setup") ==
               Enum.join(
                 [
                   Enum.join(release.install_argv, " "),
                   "regents techtree forge inspect-skill path/to/your-skill",
                   "# Then plan with a provider and model you choose:",
                   "regents techtree forge plan --help",
                   "# Every review waits for your answer."
                 ],
                 "\n"
               )

      assert copied_text(html, "copy-run-example") ==
               Enum.join(
                 [
                   Enum.join(release.install_argv, " "),
                   "regents techtree setup",
                   "regents techtree doctor --climb #{release.introductory_reference}",
                   "regents techtree skill starter",
                   "# Prepare with the Skill it placed, then run the start command it prints.",
                   "# On your ChatGPT plan:",
                   "regents techtree climb prepare #{release.introductory_reference} --skill path/to/skill --access chatgpt-plan",
                   "# Or on your own Prime key:",
                   "regents techtree climb prepare #{release.introductory_reference} --skill path/to/skill --access prime-key"
                 ],
                 "\n"
               )

      for id <- ["copy-run-instruction", "copy-run-setup", "copy-run-example"] do
        assert has_element?(live, "##{id}", "Copy")
        assert has_element?(live, "##{id}-status[role=status]")
      end

      [instruction_at, setup_at, example_at] =
        Enum.map(
          ["copy-run-instruction", "copy-run-setup", "copy-run-example"],
          &(:binary.match(html, &1) |> elem(0))
        )

      assert instruction_at < setup_at and setup_at < example_at
      refute has_element?(live, "#run-unavailable")
    end
  end

  # A reader pays for the example's model calls on their own key, so what the
  # page tells them — the model, the route, the tasks and the limits — has to be
  # what the Climb's Campaign declares, not words that can drift from it.
  @tag :tmp_dir
  test "Run locally states the model, route, tasks and limits the example's Campaign declares",
       %{conn: conn, tmp_dir: tmp_dir} do
    bundle = CatalogFixture.copy!(tmp_dir)
    CatalogFixture.rewrite_bootstrap!(bundle, &CatalogFixture.concrete_release/1)

    CatalogFixture.rewrite_campaign!(bundle, fn campaign ->
      campaign
      |> put_in(["agents", "subject", "model", "model_id"], "example/other-model")
      |> put_in(["agents", "subject", "model", "access"], ["chatgpt_plan"])
      |> update_in(["budgets"], &Map.delete(&1, "maximum_usd"))
      |> put_in(["budgets", "maximum_model_calls"], 7)
      |> put_in(["budgets", "maximum_input_tokens"], 1_234_567)
      |> put_in(["budgets", "maximum_output_tokens"], 8_000)
      |> put_in(["taskset", "selection", "num_tasks"], 5)
      |> update_in(["taskset", "membership", "ordered_task_hashes"], &Enum.take(&1, 5))
    end)

    CatalogFixture.use_bundle(bundle)
    Importer.import!(bundle)

    {:ok, _live, html} = live(conn, ~p"/docs/run-locally")
    text = visible_text(html)

    assert text =~ "example/other-model"
    assert text =~ "A ChatGPT Plus or Pro plan"
    assert text =~ "after 7 calls, 1,234,567 input tokens or 8,000 output tokens"
    assert text =~ "With 5 tasks, a run can make up to 70 model calls"
    refute text =~ "gpt-6-luna"
    refute text =~ "PRIME_API_KEY"
    refute text =~ "has spent"
  end

  test "Run locally with nothing to install offers no prompt and no command", %{conn: conn} do
    {:ok, live, html} = live(conn, ~p"/docs/run-locally")

    assert has_element?(live, "#run-unavailable")
    refute has_element?(live, "#run-unavailable[role=status]")

    for id <- ["copy-run-instruction", "copy-run-setup", "copy-run-example"] do
      refute html =~ id
    end
  end
end
