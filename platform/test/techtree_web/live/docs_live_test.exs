defmodule TechtreeWeb.DocsLiveTest do
  @moduledoc """
  The documentation is checked for four things: that a reader meets a working
  run before a concept, that what leaves the machine is answered on the way
  past, that every command named here is one the tool actually has, and that
  the page states the limits of v0.1 rather than letting a reader assume more
  than was measured.
  """

  use TechtreeWeb.ConnCase, async: false

  import Phoenix.LiveViewTest

  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture
  alias TechtreeWeb.ReleaseInfo

  describe "with the active development catalog" do
    setup do
      CatalogFixture.use_bundle(CatalogFixture.root())
      Importer.import!(CatalogFixture.root())
      :ok
    end

    test "the quickstart comes before the concepts", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/docs")
      text = visible_text(html)

      assert text =~ "Get to a controlled first run."
      assert text =~ "Give this to your Hermes agent"
      assert text =~ "Installing manually"
      assert text =~ "What leaves my machine?"
      assert text =~ "Climbs and Campaigns"
      assert text =~ "Baseline and candidate"
      assert text =~ "Taskset validation and the recorded comparison"
      assert text =~ "Proofs and reproduction"

      assert byte_offset(html, ~s|id="quickstart"|) < byte_offset(html, ~s|id="install"|)
      assert byte_offset(html, ~s|id="install"|) < byte_offset(html, ~s|id="trust"|)
      assert byte_offset(html, ~s|id="trust"|) < byte_offset(html, ~s|id="campaigns"|)
    end

    test "the quickstart shows the same prompt the installation guide shows", %{conn: conn} do
      {:ok, _live, docs_html} = live(conn, ~p"/docs")
      {:ok, _live, start_html} = live(conn, ~p"/start")

      prompt = prompt_text(docs_html)

      assert prompt != nil
      assert String.contains?(visible_text(start_html), prompt)
      assert prompt =~ "Read the pinned Techtree installation guide at"
      assert prompt =~ "Do not upload my local evaluation artifacts."
    end

    test "no held-out final test is claimed for v0.1", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/docs")
      text = visible_text(html)

      assert text =~ "There is no held-out final test in v0.1"
      assert text =~ "Hello World uses one fixed 36-task membership for its recorded comparisons."
      assert text =~ "It is not a held-out generalization claim."

      # The sidebar and the section it points at both name the recorded
      # comparison. Nothing on the page offers a held-out split.
      refute text =~ "Validation and final test"
    end

    test "what leaves the machine is answered with both halves", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/docs")
      text = visible_text(html)

      assert text =~ "Techtree sends none of this anywhere on its own"
      # Decision 0038: the list is only half the answer now. Publishing is the
      # one thing that sends anything, and the passage has to say what travels
      # when somebody asks for it or the list reads as a promise it is not.
      assert text =~ "Publishing a run is the one thing that sends anything"
      assert text =~ "This website has no account system and no route for submitting those"
      assert text =~ "A comparison still makes real model requests."

      assert text =~
               "send requests to the subject-model provider named by the Campaign, under that " <>
                 "provider’s policies"

      assert text =~ "No Techtree account is required."
    end

    test "the guided revision says what is sent and what is never sent", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/docs")
      text = visible_text(html)

      for sent <- [
            "the verified source Skill;",
            "the founder-pinned Skill-improver instructions;",
            "a sanitized summary of the measured run; and",
            "a strict required response shape."
          ] do
        assert text =~ sent
      end

      assert text =~
               "It does not receive hidden expected answers, grader source, provider " <>
                 "credentials, local private paths, or the evaluated subject’s final replies."

      assert text =~
               "The sanitized summary excludes hidden expected answers, grader source, " <>
                 "provider credentials, private filesystem paths, and the evaluated " <>
                 "subject’s final replies."
    end

    test "the install-time report is described with its verdict and left switched on",
         %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/docs")
      text = visible_text(html)

      assert text =~
               "Hermes is expected to report caution with five reviewed findings in " <>
                 "three families"

      assert text =~ "Read the report before approving installation."
      assert text =~ "Never turn the scanning off."
    end

    test "stand-in coordinates are described but never offered", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/docs")
      text = visible_text(html)

      assert text =~ "No installable release is active on this channel yet."
      assert text =~ "No installable release coordinate is active on this channel yet."
      refute html =~ "techtree==0.0.0-placeholder"
      refute html =~ String.duplicate("0", 40)
    end

    test "the reference names only commands that actually ship", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/docs")
      text = visible_text(html)

      for command <- [
            "techtree doctor",
            "techtree setup",
            "techtree climb",
            "techtree skill",
            "techtree run",
            "techtree engine",
            "techtree proof",
            "techtree release",
            "techtree uplift"
          ] do
        assert text =~ command
      end

      assert text =~ "The command list above is the complete v0.1 CLI namespace."

      # Three commands a reader could reasonably expect and this build does not
      # have. Naming one would be an instruction that fails on their machine.
      refute text =~ ~r/\btechtree up\b/
      refute text =~ "techtree harness"
      refute text =~ "techtree dashboard"
    end

    test "the deferred surfaces are absent rather than promised", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/docs")
      text = visible_text(html)

      refute text =~ "v0.2"
      refute text =~ "Harness support"
      refute text =~ "Codex"
      refute text =~ "Local dashboard"
      refute text =~ "coming soon"
    end

    test "the guided revision is labelled experimental and promises nothing",
         %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/docs")
      text = visible_text(html)

      assert text =~ "Experimental"
      assert text =~ "A proposal may be unusable. A valid proposal may improve, tie, or regress."
      assert text =~ "Techtree does not automatically retry the proposal."
    end

    test "machine mode is stated the way an agent needs it", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/docs")
      text = visible_text(html)

      assert text =~ "--json implies --no-input ;"
      assert text =~ "machine output contains one JSON object on stdout;"
      assert text =~ "operational logs go to stderr;"
      assert text =~ "the command never waits for interactive input."
    end

    test "the exit codes are listed with the meaning of each", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/docs")
      text = visible_text(html)

      assert text =~ "A host agent may branch on exit codes without parsing human text."

      for {code, meaning} <- [
            {"0", "Finished as requested."},
            {"1", "An internal or otherwise unclassified error."},
            {"2", "The command or its arguments were used incorrectly."},
            {"3", "Input or stored data failed validation."},
            {"4", "A prerequisite is missing."},
            {"5", "The requested object does not exist."},
            {"6", "The request conflicts with existing immutable state."},
            {"7", "A credential is missing, expired, or refused."},
            {"8", "A data or publication policy forbids the request."},
            {"9", "The managed evaluation engine failed."},
            {"10", "The run failed or the requested run operation is invalid in its current"},
            {"11",
             "A digest, signature, membership commitment, report, or proof did not verify."},
            {"130", "Cancelled."}
          ] do
        assert text =~ "#{code} #{meaning}", "exit code #{code} is not listed with its meaning"
      end
    end

    test "the supported variables are the real ones and the internal one says so",
         %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/docs")
      text = visible_text(html)

      assert text =~ "TECHTREE_OUTPUT_MODE"
      assert text =~ "TECHTREE_LOG_LEVEL"
      assert text =~ "TECHTREE_ACTIVE_ENGINE_DIGEST"
      assert text =~ "No other TECHTREE_* setting is inferred or guessed."

      assert text =~
               "TECHTREE_HOME is used internally when the CLI starts its detached worker. " <>
                 "It is not the documented user-facing replacement for --home"
    end

    test "the credential path is the Prime login, not an exported key", %{conn: conn} do
      {:ok, live, html} = live(conn, ~p"/docs")
      text = visible_text(html)

      assert text =~ "Hello World requires an active Prime CLI login."

      assert text =~
               "An exported PRIME_API_KEY in the shell is not the supported detached-run " <>
                 "path and is deliberately not inherited as ambient worker state."

      assert text =~
               "Techtree does not store, print, or copy the provider credential into a " <>
                 "draft, run directory, receipt, report, or proof bundle."

      assert live
             |> element(~s|#copy-docs-prime-login[data-copy-value="prime login"]|)
             |> has_element?()
    end

    test "a proof is verified from one of three things, offline", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/docs")
      text = visible_text(html)

      assert text =~ "You can verify a run ID, a proof-bundle directory, or a signed report file"
      assert text =~ "makes no model request;"
      assert text =~ "contacts no Techtree service;"
      assert text =~ "fetches nothing from the network; and"
      assert text =~ "writes nothing to the proof."
    end

    test "every command block can be copied", %{conn: conn} do
      {:ok, live, html} = live(conn, ~p"/docs")

      blocks = Regex.scan(~r/class="command__block"/, html) |> length()
      copies = Regex.scan(~r/phx-hook="CopyCommand"/, html) |> length()

      assert blocks > 0
      assert blocks == copies

      assert live
             |> element(
               ~s|#copy-docs-proof-verify[data-copy-value="techtree proof verify path/to/result-bundle"]|
             )
             |> has_element?()
    end
  end

  @tag :tmp_dir
  test "a real release drives the install step and the release coordinates", %{
    conn: conn,
    tmp_dir: tmp_dir
  } do
    bundle = CatalogFixture.copy!(tmp_dir)
    CatalogFixture.rewrite_bootstrap!(bundle, &CatalogFixture.concrete_release/1)
    CatalogFixture.use_bundle(bundle)
    Importer.import!(bundle)

    release = ReleaseInfo.current()
    {:ok, live, html} = live(conn, ~p"/docs")
    text = visible_text(html)

    assert live
           |> element(
             ~s|#copy-docs-install[data-copy-value="uv tool install --python 3.12 techtree==0.1.0"]|
           )
           |> has_element?()

    assert text =~ release.digest
    assert text =~ release.source_revision
    assert text =~ "techtree doctor --climb hello-world-climb@1"
    assert text =~ "macOS or Linux · Python 3.12, provided by the installer · Docker required"

    # The coordinates come out of the record, never out of this page.
    assert text =~ release.version
    assert text =~ release.starter_skill["file_digest"]
    assert text =~ release.starter_skill["tree_digest"]
    refute text =~ "No installable release coordinate is active on this channel yet."
  end

  defp byte_offset(haystack, needle) do
    {offset, _length} = :binary.match(haystack, needle)
    offset
  end

  # The prompt as a reader sees it, taken from the block they copy.
  defp prompt_text(html) do
    case Regex.run(~r|<pre class="prompt__block"><code>(.*?)</code></pre>|s, html,
           capture: :all_but_first
         ) do
      [prompt] -> prompt |> String.replace(~r/\s+/, " ") |> String.trim()
      _other -> nil
    end
  end

  describe "the substrate credits" do
    setup do
      Techtree.CatalogFixture.use_bundle(Techtree.CatalogFixture.root())
      Techtree.Catalog.Importer.import!(Techtree.CatalogFixture.root())
      :ok
    end

    test "Verifiers is credited to Prime Intellect with the exact pinned version", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/docs")
      text = Phoenix.LiveViewTest.rendered_to_string(html)

      assert text =~ "Prime Intellect’s Verifiers"
      # The pin is verifiers 0.3.1 (founder ruling 2026-08-26; the python-side
      # switch from 0.3.1.dev21 lands with the same ruling). If the pin moves,
      # this copy must move with it — that is what these lines are for.
      assert text =~ "pinned at version 0.3.1"
      refute text =~ "dev21"
    end

    test "Hermes is credited to Nous Research on the pages that name the stack", %{conn: conn} do
      for page <- ["/", "/docs"] do
        {:ok, _live, html} = live(conn, page)
        assert html =~ "Nous Research", "#{page} does not credit Hermes to Nous Research"
      end
    end

    test "the page offers itself as Markdown through the copy control", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/docs")

      assert html =~ ~s|phx-hook="CopyCommandPage"|
      assert html =~ ~s|phx-hook="CopyCommandPageView"|
      assert html =~ "Copy page as Markdown for agents"
      assert html =~ "View as Markdown"
      # The control never talks to the server and is excluded from its own copy.
      assert html =~ "data-markdown-skip"
    end

    test "the release label names the product and version", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/docs")
      text = visible_text(html)

      assert text =~ "Techtree v0.1"
      refute text =~ "Local preview"
    end
  end
end
