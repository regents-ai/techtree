defmodule TechtreeWeb.HomeLiveTest do
  @moduledoc """
  The landing page answers "what is this?" before "who are you?", and every
  number on it comes from a document this release publishes.

  Five regions, in one order, with one way in. What is checked here is the
  wording that was decided rather than written, the coordinates that must be
  read rather than typed, and the two things this page must never grow: an
  invented figure and a second installation path.
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

    test "the v0.1 section credits the agent stack and names the next integration",
         %{conn: conn} do
      {:ok, live, html} = live(conn, ~p"/")
      text = visible_text(html)

      assert has_element?(
               live,
               ".proof-of-concept .eyebrow",
               "hermes + prime + nvidia agent stack"
             )

      assert has_element?(
               live,
               "#what-this-release-is",
               "v0.1 release - standing on giants"
             )

      assert has_element?(
               live,
               ~s|a[href="https://github.com/PrimeIntellect-ai/verifiers"]|,
               "Prime Intellect’s Verifiers"
             )

      assert has_element?(
               live,
               ~s|a[href="https://github.com/NousResearch/hermes-agent"]|,
               "Nous Research’s Hermes"
             )

      assert has_element?(
               live,
               ~s|.what-this-is__roadmap a[href="https://github.com/NVIDIA-NeMo"]|,
               "NeMo Framework"
             )

      assert text =~ "Support for NVIDIA’s NeMo Framework coming in v0.2."
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

      assert live |> element(~s|a.button--primary[href="/docs#quickstart"]|) |> has_element?()
      assert live |> element(~s|a[href="/runs"]|, "View published runs") |> has_element?()

      # The agent-and-human fork moved to the installation guide; the front
      # page no longer asks a reader to choose before they know what for.
      refute text =~ "My agent is installing"
      refute text =~ "I’m installing"
      refute text =~ "Give this to your Hermes agent"
      refute text =~ "Prefer installing it yourself?"
    end

    test "the hero hands an agent one line, copyable in one action", %{conn: conn} do
      {:ok, live, html} = live(conn, ~p"/")

      assert visible_text(html) =~
               "Go to techtree.sh/start and set up Techtree and run the Hello World Climb."

      assert live
             |> element(
               ~s|#copy-home-agent-line[data-copy-value="Go to techtree.sh/start and set up | <>
                 ~s|Techtree and run the Hello World Climb."]|
             )
             |> has_element?()
    end

    test "the two ways in are separated, with the agent's line first", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/")
      text = visible_text(html)

      assert [{agent_at, _} | _] = :binary.matches(text, "Give this to your agent")
      assert [{divider_at, _} | _] = :binary.matches(text, "Or use the CLI directly")

      assert agent_at < divider_at,
             "the line for the agent has to come before the divider that separates it " <>
               "from the path for somebody typing"
    end

    test "the page holds exactly the five regions it was given", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/")

      sections = Regex.scan(~r/<section[^>]*class="([^"]*)"/, html, capture: :all_but_first)

      assert [
               ["hero"],
               ["home-section proof-of-concept"],
               ["home-section process"],
               ["home-section featured"],
               ["home-section trust"]
             ] =
               Enum.reject(sections, fn [class] ->
                 String.starts_with?(class, "evidence-graph")
               end)
    end

    test "the three steps read as they were written", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/")
      text = visible_text(html)

      assert text =~ "Resolve a pinned campaign and record the baseline."
      assert text =~ "Change one declared Skill under a fixed budget and validation rule."

      assert text =~
               "Sign the comparison, read the outcome of every task, and check the receipt offline."
    end

    test "the graph and the featured campaign come out of the imported catalog",
         %{conn: conn} do
      {:ok, live, html} = live(conn, ~p"/")
      text = visible_text(html)

      assert has_element?(live, ".proof-of-concept #home-evidence-graph")
      refute has_element?(live, ".hero #home-evidence-graph")

      assert has_element?(
               live,
               ~s|#hero-crown[phx-hook="Optics"][data-optics-kind="crown"] canvas[data-optics-canvas]|
             )

      assert text =~ CatalogFixture.campaign_digest()
      assert text =~ "prime · qwen/qwen3.7-flash"
      assert text =~ "36 tasks, fixed before either run"
      assert text =~ "36 tasks validated"
      assert text =~ "Hello World Skill Uplift"

      assert live
             |> element(~s|a[href="/campaigns/hello-world-climb"]|, "Inspect the campaign")
             |> has_element?()
    end

    test "the trust region says where the model calls go and who attested the run",
         %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/")
      text = visible_text(html)

      assert text =~ "Techtree uploads nothing on its own"
      assert text =~ "publishing sends the receipt rather than the recordings"
      assert text =~ "go to the model provider you selected, under that provider’s policies"
      assert text =~ "attested by the participant who produced it"
      assert text =~ "Nobody else watched the run"
    end

    test "a stand-in release is described and never handed over as a command", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/")

      assert visible_text(html) =~ "This channel publishes stand-in coordinates"
      refute html =~ "techtree==0.0.0-placeholder"
      refute html =~ String.duplicate("0", 40)
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

  describe "with a concrete release published" do
    @tag :tmp_dir
    test "the install command and its label are read from the release",
         %{conn: conn, tmp_dir: tmp_dir} do
      bundle = CatalogFixture.copy!(tmp_dir)
      CatalogFixture.rewrite_bootstrap!(bundle, &CatalogFixture.concrete_release/1)
      CatalogFixture.use_bundle(bundle)
      Importer.import!(bundle)

      {:ok, live, html} = live(conn, ~p"/")

      assert live
             |> element(
               ~s|#copy-home-install[data-copy-value="uv tool install --python 3.12 techtree==0.1.0"]|
             )
             |> has_element?()

      # The first thing to run afterwards, with the Climb it checks read from
      # the same release record the install command came from.
      assert live
             |> element(
               ~s|#copy-home-doctor[data-copy-value="techtree doctor --climb #{CatalogFixture.climb_reference()}"]|
             )
             |> has_element?()

      assert visible_text(html) =~
               "macOS or Linux · uv required · Docker required · Python 3.12 managed by uv · " <>
                 "Hermes 0.20.1+ only for the plugin path"

      assert visible_text(html) =~
               "Doctor checks prerequisites and prints the exact next action. " <>
                 "These commands do not start paid model inference."

      text = visible_text(html)
      assert {actions_at, _actions_length} = :binary.match(text, "View published runs")
      assert {doctor_at, _doctor_length} = :binary.match(text, "Doctor checks prerequisites")
      assert actions_at < doctor_at

      assert html =~
               ~s|class="masthead__github" href="https://github.com/regents-ai/techtree"|

      assert html =~ ~s|aria-label="regents-ai/techtree on GitHub, 0 stars"|
    end
  end

  test "the landing page needs no catalog to render", %{conn: conn} do
    {:ok, _live, html} = live(conn, ~p"/")
    text = visible_text(html)

    assert text =~ "Improve a Skill."
    assert text =~ "No release is published on this channel yet."
    refute text =~ "Evidence graph"

    # The line for the agent names no coordinate, so it survives; the half of
    # the panel that would need one is not printed at all.
    assert text =~ "Go to techtree.sh/start"
    refute html =~ "copy-home-install"
    refute html =~ "copy-home-doctor"
  end

  test "the project source link does not depend on a published release", %{conn: conn} do
    CatalogFixture.use_bundle(CatalogFixture.root())
    Importer.import!(CatalogFixture.root())

    {:ok, _live, html} = live(conn, ~p"/")

    assert html =~
             ~s|class="masthead__github" href="https://github.com/regents-ai/techtree" target="_blank"|
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
               ~r|<span class="masthead__selector">.*href="/runs"[^>]*>\s*Run\s*</a>.*href="/proofs"[^>]*>\s*Proofs\s*</a>.*href="/docs"[^>]*>\s*Docs\s*</a>.*</span>\s*<a class="masthead__github" href="https://github.com/regents-ai/techtree"|s

      assert html =~ ~r|</nav>\s*<button id="site-theme-toggle"|s
      assert html =~ ~s|class="theme-toggle__cube"|
      assert html =~ ~s|class="theme-toggle__laser"|
      assert has_element?(live, "main")
      assert html =~ "A Regents Labs project"
      refute html =~ ~s|>Sign in<|
    end
  end
end
