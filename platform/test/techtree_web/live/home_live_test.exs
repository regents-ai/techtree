defmodule TechtreeWeb.HomeLiveTest do
  @moduledoc """
  The landing page answers "what is this?" before "who are you?", and every
  number on it comes from a document this release publishes.

  Four regions, in one order, with one way in. What is checked here is the
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
      {:ok, _live, html} = live(conn, ~p"/")
      text = visible_text(html)

      assert text =~ "Improve a Skill."
      assert text =~ "Prove it worked."

      assert text =~
               "Run a controlled baseline and candidate on your machine. Techtree keeps the " <>
                 "taskset, model, harness, tools, and budget fixed, then signs the result so " <>
                 "anyone holding a copy can check it offline, needing no account and " <>
                 "nothing from us."

      assert text =~ "Techtree v0.1 · development release"
    end

    test "there is one way in, and it is the same one for everybody", %{conn: conn} do
      {:ok, live, html} = live(conn, ~p"/")
      text = visible_text(html)

      assert live |> element(~s|a.button--primary[href="/docs#install"]|) |> has_element?()
      assert live |> element(~s|a[href="/proofs"]|, "View a verified run") |> has_element?()

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
      assert [{divider_at, _} | _] = :binary.matches(text, "Or install it yourself")

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

      assert has_element?(live, "#home-evidence-graph")
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
    test "the install command, its label and the source link are read from the release",
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

      assert visible_text(html) =~ "macOS or Linux · Python 3.12"
      assert visible_text(html) =~ "Docker required"

      assert live
             |> element(
               ~s|a.masthead__source[href="https://github.com/regents-ai/techtree-hermes/tree/#{String.duplicate("a", 40)}"]|
             )
             |> has_element?()
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

  test "the source link is shown only when the release names one immutable revision",
       %{conn: conn} do
    CatalogFixture.use_bundle(CatalogFixture.root())
    Importer.import!(CatalogFixture.root())

    {:ok, live, _html} = live(conn, ~p"/")

    refute live |> element("a.masthead__source") |> has_element?()
  end

  test "every page carries the same three ways on", %{conn: conn} do
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
      {:ok, _live, html} = live(conn, path)

      assert html =~ ~s|href="/docs"|, "#{path} does not link to the documentation"
      assert html =~ ~s|href="/proofs"|, "#{path} does not link to a proof"
      assert html =~ "A Regents Labs project"
      refute html =~ ~s|>Sign in<|
    end
  end
end
