defmodule TechtreeWeb.HomeLiveTest do
  @moduledoc """
  The landing page explains why Techtree exists and gives an agent one way in.
  """

  use TechtreeWeb.ConnCase, async: false

  import Phoenix.LiveViewTest

  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture

  describe "with a release published" do
    setup do
      CatalogFixture.use_bundle(CatalogFixture.root())
      Importer.import!(CatalogFixture.root())
      :ok
    end

    test "the hero says what this is, in the words it was decided in", %{conn: conn} do
      {:ok, live, html} = live(conn, ~p"/")
      text = visible_text(html)

      assert text =~ "Improve a Skill."
      assert text =~ "Prove it worked."
      assert text =~ "Same pinned agent. Same fixed tasks. One changed Skill."
      assert text =~ "Get a signed local receipt for the difference."

      assert has_element?(
               live,
               "#hero-title > .hero-title__line",
               "Improve a Skill."
             )

      assert has_element?(live, "#hero-title > .hero-title__line", "Prove it worked.")

      assert text =~ "Techtree v0.1 · development release"
    end

    test "the crown comparison route renders the same 13-cube homepage", %{conn: conn} do
      {:ok, live, html} = live(conn, ~p"/crown/1")

      assert visible_text(html) =~ "Improve a Skill."

      assert has_element?(
               live,
               ~s|#hero-crown[phx-hook="Optics"][phx-update="ignore"][data-optics-kind="crown"][data-crown-variant="1"] canvas[data-optics-canvas]|
             )

      assert has_element?(live, "#crown-study-1[aria-current=page]")
    end

    test "the hero points to the release section below it", %{conn: conn} do
      {:ok, live, _html} = live(conn, ~p"/")

      assert has_element?(
               live,
               ~s|a.hero__more[href="#what-this-release-is"][aria-label="Continue to the v0.1 release section"] svg|
             )
    end

    test "the page keeps release, installation, and proof teaching on their own routes",
         %{conn: conn} do
      {:ok, live, html} = live(conn, ~p"/")
      text = visible_text(html)

      assert has_element?(live, ~s|a[href="/start"]|, "Start your first Climb")
      assert has_element?(live, "#copy-home-agent-line")
      refute text =~ "Or use the CLI directly"
      refute text =~ "Release integrity"
      refute text =~ "What verification establishes"
    end

    test "the hero omits the retired explanatory copy", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/")
      text = visible_text(html)

      refute text =~ "Run a controlled baseline and candidate on your machine."
      refute text =~ "It reads the pinned installation guide"
      refute text =~ "No Techtree account"

      refute text =~
               "Those are the seams of the stack, and this site names them rather than leaving a reader to find them."
    end

    test "there is one way in, and it is the same one for everybody", %{conn: conn} do
      {:ok, live, html} = live(conn, ~p"/")
      text = visible_text(html)

      assert live |> element(~s|a.button--primary[href="/start"]|) |> has_element?()
      assert live |> element(~s|a[href="/results"]|, "View published Results") |> has_element?()

      # The agent-and-human fork moved to the installation guide; the front
      # page no longer asks a reader to choose before they know what for.
      refute text =~ "My agent is installing"
      refute text =~ "I’m installing"
      refute text =~ "Give this to your Hermes agent"
      refute text =~ "Prefer installing it yourself?"
    end

    test "the lower homepage sections remain available below the hero", %{conn: conn} do
      {:ok, live, html} = live(conn, ~p"/")
      text = visible_text(html)

      assert has_element?(live, "#what-this-release-is")
      assert has_element?(live, "#home-evidence-graph")
      assert has_element?(live, ".home-section.process")
      assert has_element?(live, ".home-section.featured")
      assert has_element?(live, ".home-section.trust")
      assert text =~ "v0.1 release - standing on giants"
      assert text =~ "Run. Improve. Prove."
      assert text =~ "Published by this release"
      assert text =~ "Your work stays local."
    end

    test "the hero gives an agent the copyable setup instruction instead of a Result",
         %{conn: conn} do
      {:ok, live, html} = live(conn, ~p"/")
      text = visible_text(html)

      assert has_element?(live, "#home-evidence-graph")
      refute has_element?(live, ".hero-result")

      assert has_element?(
               live,
               ~s|#hero-crown[phx-hook="Optics"][data-optics-kind="crown"] canvas[data-optics-canvas]|
             )

      assert text =~ "Give this to your agent"

      assert text =~
               "Go to techtree.sh/start and set up Techtree and run the Hello World Climb."

      assert has_element?(
               live,
               ~s|#copy-home-agent-line[data-copy-value="Go to techtree.sh/start and set up Techtree and run the Hello World Climb."]|
             )

      refute text =~ "One concrete Result"
      refute text =~ "Instructional Skill vs No Skill"
    end

    test "the page invents no activity and claims no independent checking", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/")

      for fabrication <- [
            "participants so far",
            "runs completed",
            "leaderboard",
            "trending",
            "join thousands",
            "independently verified",
            "verified by techtree"
          ] do
        refute String.downcase(html) =~ fabrication
      end

      refute html =~ ~r/\d+\s+(participants|teams|runs|submissions)\b/i
      refute html =~ ~r/\+\d+(\.\d+)?%/
    end
  end

  test "the landing page needs no catalog to render", %{conn: conn} do
    {:ok, _live, html} = live(conn, ~p"/")
    text = visible_text(html)

    assert text =~ "Improve a Skill."
    refute text =~ "Evidence graph"
    assert text =~ "Start your first Climb"
    assert text =~ "Go to techtree.sh/start and set up Techtree and run the Hello World Climb."
    refute html =~ "copy-home-cli"
  end

  test "the project source link does not depend on a published release", %{conn: conn} do
    CatalogFixture.use_bundle(CatalogFixture.root())
    Importer.import!(CatalogFixture.root())

    {:ok, _live, html} = live(conn, ~p"/")

    assert html =~
             ~s|class="masthead__github" href="https://github.com/regents-ai/techtree" target="_blank"|
  end

  test "the landing page leaves every primary tab neutral", %{conn: conn} do
    {:ok, _live, html} = live(conn, ~p"/")

    refute html =~ ~s|aria-current="page"|
    assert html =~ ~s|<a class="masthead__name" href="/" aria-label="Techtree home">|
    refute html =~ ~s|<a class="masthead__name" data-phx-link|
  end

  test "every page carries the same primary navigation in the decided order", %{conn: conn} do
    CatalogFixture.use_bundle(CatalogFixture.root())
    Importer.import!(CatalogFixture.root())

    for path <- [
          ~p"/",
          ~p"/docs",
          ~p"/campaigns",
          ~p"/campaigns/hello-world-climb",
          ~p"/proofs",
          ~p"/start",
          ~p"/climbs",
          ~p"/proofs/local",
          ~p"/protocol"
        ] do
      {:ok, live, html} = live(conn, path)

      assert html =~
               ~r|<span class="masthead__selector">.*href="/results"[^>]*>\s*Results\s*</a>.*href="/proofs"[^>]*>\s*Proofs\s*</a>.*href="/docs"[^>]*>\s*Docs\s*</a>.*</span>\s*<a class="masthead__github" href="https://github.com/regents-ai/techtree"|s

      assert html =~ ~r|</nav>\s*<button id="site-theme-toggle"|s
      assert html =~ ~s|class="theme-toggle__cube"|
      assert html =~ ~s|class="theme-toggle__laser"|
      assert has_element?(live, "main")
      assert html =~ "A Regents Labs project"
      refute html =~ ~s|>Sign in<|
    end
  end
end
