defmodule TechtreeWeb.HomeLiveTest do
  @moduledoc """
  The landing page explains why Techtree exists and gives both installation paths.
  """

  use TechtreeWeb.ConnCase, async: false

  import Phoenix.LiveViewTest

  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture
  alias Techtree.NetworkFixture
  alias TechtreeWeb.HomeLive

  describe "with a release published" do
    setup do
      CatalogFixture.use_bundle(CatalogFixture.root())
      Importer.import!(CatalogFixture.root())
      :ok
    end

    test "the hero makes one promise and offers one Start button", %{conn: conn} do
      {:ok, live, html} = live(conn, ~p"/")
      text = visible_text(html)

      assert has_element?(live, "#hero-title", "Improve a Skill. Prove it worked.")
      assert text =~ "Run the same tasks with and without your Skill."
      assert has_element?(live, ~s|.hero__actions a.rg-button--primary[href="/start"]|, "Start")

      assert [_one] =
               html
               |> LazyHTML.from_fragment()
               |> LazyHTML.query(".hero .rg-button--primary")
               |> Enum.to_list()

      refute has_element?(live, ~s|.hero a[href="/repo2rlenv"]|)
      refute has_element?(live, "#hero-outcome")
      assert has_element?(live, "section.hero")
      refute text =~ "Controlled agent evaluations"
    end

    test "the copy remains visible beside a bounded crown canvas", %{conn: conn} do
      {:ok, live, _html} = live(conn, ~p"/")
      css = File.read!("assets/css/app.css")
      javascript = File.read!("assets/js/app.ts")

      assert has_element?(live, ".hero__copy")
      refute css =~ "hero-reveal-failsafe"
      refute javascript =~ "heroFallback"
      refute javascript =~ "hero.dataset.heroStage"
      refute javascript =~ "siteBackgroundController?.mount()"
      refute has_element?(live, "#site-background-canvas")
      assert has_element?(live, "#hero-crown canvas#hero-crown-canvas")
      assert css =~ ~s|@import "./techtree_home.css"|
    end

    test "the hero points to how a Skill is tested, with the wallet tests further down",
         %{conn: conn} do
      {:ok, live, html} = live(conn, ~p"/")

      assert has_element?(live, ~s|a.hero__more[href="#skill-test"] svg|)

      {skill_test, _length} = :binary.match(html, ~s|id="skill-test"|)
      {wallet_bench, _length} = :binary.match(html, ~s|id="wallet-bench"|)
      assert skill_test < wallet_bench
    end

    test "the page keeps release and proof teaching on their own routes",
         %{conn: conn} do
      {:ok, live, html} = live(conn, ~p"/")
      text = visible_text(html)

      assert has_element?(live, "#copy-home-agent-line")
      assert has_element?(live, ".installer__manual > summary", "Use the command line instead")
      refute text =~ "Release integrity"
      assert has_element?(live, ~s|a[href="/verify"]|, "What verification establishes")
    end

    @tag :tmp_dir
    test "the manual path is one copyable release-derived block", %{conn: conn, tmp_dir: tmp_dir} do
      bundle = CatalogFixture.copy!(tmp_dir)
      CatalogFixture.rewrite_bootstrap!(bundle, &CatalogFixture.concrete_release/1)
      CatalogFixture.use_bundle(bundle)
      Importer.import!(bundle)

      {:ok, live, html} = live(conn, ~p"/")
      release = TechtreeWeb.ReleaseInfo.current()

      expected =
        Enum.join(release.install_argv, " ") <>
          "\n" <>
          "regents techtree forge inspect-skill path/to/your-skill"

      assert has_element?(live, "#copy-home-cli")
      assert copied_text(html, "copy-home-cli") == expected
      refute html =~ "Doctor checks prerequisites"

      assert has_element?(live, ".installer__manual .command", "Install, then look at your Skill")
      refute has_element?(live, ".installer__doctor-note")
      refute has_element?(live, ".compatibility")
      refute has_element?(live, ".release-coordinate")
      refute html =~ "These commands do not start paid model inference."
      refute html =~ "macOS or Linux · uv required"
      refute html =~ "Release details"
      refute has_element?(live, "#copy-home-install")
      refute has_element?(live, "#copy-home-doctor")
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

    test "the agent path stays first and the route actions stay stable", %{conn: conn} do
      {:ok, live, html} = live(conn, ~p"/")
      text = visible_text(html)

      assert has_element?(live, "#copy-home-agent-line", "Copy")

      assert live
             |> element(~s|#skill-test a[href="/examples/tdd"]|, "See a real comparison")
             |> has_element?()

      assert live
             |> element(~s|.installer__manual a[href="/start"]|, "Every way to start")
             |> has_element?()

      assert live |> element(~s|a[href="/results"]|, "Published Results") |> has_element?()

      refute text =~ "My agent is installing"
      refute text =~ "I’m installing"
      refute text =~ "Give this to your Hermes agent"
      refute text =~ "Prefer installing it yourself?"
    end

    test "the lower homepage sections remain available below the hero", %{conn: conn} do
      {:ok, live, _html} = live(conn, ~p"/")

      assert has_element?(live, "#capabilities")
      assert has_element?(live, ~s|#wallet-bench a[href="/wallet-bench"]|, "See the wallet tests")
      assert has_element?(live, "#tools #tool-skill2env h3", "Skill2Env")
      assert has_element?(live, "#tools #tool-repo2rlenv h3", "Repo2RLEnv")
      assert has_element?(live, "#tools #tool-tasksmith h3", "Tasksmith")
      assert has_element?(live, "#tools #tool-frontiersmith h3", "FrontierSmith")
      refute has_element?(live, "#home-evidence-graph")
      refute has_element?(live, ".home-section.process")
      assert has_element?(live, "#skill-test")
      assert has_element?(live, "#quick-look.featured")
      assert has_element?(live, ".home-section.trust")
    end

    test "with nothing published, the hero gives an agent the instruction and no Result",
         %{conn: conn} do
      {:ok, live, html} = live(conn, ~p"/")
      text = visible_text(html)

      refute has_element?(live, "#home-evidence-graph")
      refute has_element?(live, ".hero-result")

      assert has_element?(
               live,
               ~s|#hero-crown canvas#hero-crown-canvas|
             )

      assert text =~ "Paste into your agent’s chat"
      assert text =~ HomeLive.agent_line()

      assert copied_text(html, "copy-home-agent-line") == HomeLive.agent_line()

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

  describe "with a Result published" do
    setup do
      CatalogFixture.use_bundle(CatalogFixture.root())
      Importer.import!(CatalogFixture.root())
      files = NetworkFixture.resign(NetworkFixture.scored(), keys: NetworkFixture.key_pair())
      {:ok, entry, :recorded} = NetworkFixture.publish(NetworkFixture.submission(files))
      {:ok, entry: entry}
    end

    test "the newest Result sits under the promise, with how sure it is", %{
      conn: conn,
      entry: entry
    } do
      {:ok, live, _html} = live(conn, ~p"/")

      card = ~s|#hero-newest-result[href="/results/#{entry.bundle_digest}"]|
      verdict = entry.assessment |> Techtree.Network.Verdict.of() |> Atom.to_string()

      assert has_element?(live, card, "Hello World Skill vs baseline")
      assert has_element?(live, "#{card} .verdict--#{verdict}")

      assert has_element?(
               live,
               card,
               "#{entry.wins} better · #{entry.ties} same · #{entry.losses} worse · 1 run"
             )
    end
  end

  test "the landing page needs no catalog to render", %{conn: conn} do
    {:ok, _live, html} = live(conn, ~p"/")
    text = visible_text(html)

    assert text =~ "Improve a Skill. Prove it worked."
    refute text =~ "Evidence graph"
    assert text =~ HomeLive.agent_line()
    refute html =~ "copy-home-cli"
  end

  test "the project source link does not depend on a published release", %{conn: conn} do
    CatalogFixture.use_bundle(CatalogFixture.root())
    Importer.import!(CatalogFixture.root())

    {:ok, _live, html} = live(conn, ~p"/")

    assert html =~
             ~s|class="masthead__github" href="https://github.com/regents-ai/techtree" target="_blank"|

    assert html =~ "Star on GitHub"
    refute html =~ "masthead__github-mark"
  end

  test "the sheet shares canonical type, spacing and control skins" do
    css = File.read!(Path.expand("../../../assets/css/app.css", __DIR__))

    assert css =~ ~s|@import "../vendor/regent_ui/primitives.css"|
    assert css =~ "font-family: var(--font-family-ui)"
    assert css =~ "font-family: var(--font-family-title)"
    assert css =~ "font-synthesis: none"
    refute css =~ "100vw;"
    refute css =~ "text-overflow: ellipsis"
  end

  test "small-screen controls retain data and intentional table scrolling" do
    css = File.read!(Path.expand("../../../assets/css/app.css", __DIR__))

    assert css =~ "@media (max-width: 24rem)"
    assert css =~ "grid-template-columns: minmax(0, 1fr)"
    assert css =~ ".runs-index__table-frame"
    assert css =~ "overflow-x: auto"
    refute css =~ ~r/\.runs-table__runtime\s*\{[^}]*display: none/s
    assert css =~ ~r/\.command__copy\s*\{[^}]*min-height: 2\.75rem;/s
    assert css =~ ~r/\.tasks__filter\s*\{[^}]*min-height: 2\.75rem;/s
    assert css =~ ~r/\.pagecopy__main\s*\{[^}]*min-height: 2\.75rem;/s
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
          ~p"/results",
          ~p"/verify",
          ~p"/start",
          ~p"/climbs/hello-world-climb"
        ] do
      {:ok, live, html} = live(conn, path)

      assert html =~
               ~r|<span class="masthead__selector">.*href="/start"[^>]*>\s*Start\s*</a>.*href="/results"[^>]*>\s*Results\s*</a>.*href="/verify"[^>]*>\s*Check a Result\s*</a>.*href="/docs"[^>]*>\s*Docs\s*</a>.*</span>\s*<a class="masthead__github" href="https://github.com/regents-ai/techtree"|s

      refute html =~ ~r|href="/results"[^>]*>\s*Proofs\s*</a>|

      if path == ~p"/start" do
        assert html =~ ~r|href="/start" aria-current="page">\s*Start\s*</a>|
      end

      assert html =~ ~r|</nav>\s*<button[^>]*id="site-theme-toggle"|s
      assert html =~ ~s|rg-button--secondary theme-toggle|
      assert html =~ ~s|class="theme-toggle__cube"|
      assert has_element?(live, "main")

      assert html =~
               ~r|<a class="skip-link" href="#main-content">\s*Skip to main content\s*</a>|

      assert has_element?(live, "main#main-content")
      assert has_element?(live, "footer.regent-footer")
      refute html =~ ~s|>Sign in<|
    end
  end
end
