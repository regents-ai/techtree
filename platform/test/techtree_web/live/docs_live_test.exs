defmodule TechtreeWeb.DocsLiveTest do
  @moduledoc """
  The documentation is checked for three things: that a reader meets a working
  run before a concept, that what leaves the machine is answered on the way
  past, and that every command named here is one the tool actually has.
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
      assert text =~ "What leaves my machine?"
      assert text =~ "Baseline and candidate"
      assert text =~ "Validation and final test"
      assert text =~ "Proofs and reproduction"

      assert byte_offset(html, ~s|id="quickstart"|) < byte_offset(html, ~s|id="trust"|)
      assert byte_offset(html, ~s|id="trust"|) < byte_offset(html, ~s|id="campaigns"|)
    end

    test "what leaves the machine is answered with both halves", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/docs")
      text = visible_text(html)

      assert text =~ "Techtree does not upload your recordings"
      assert text =~ "there is nowhere on this site to send them"
      assert text =~ "make real model calls"
      assert text =~ "go to the model provider the campaign names, under that provider’s policies"
      assert text =~ "It needs no Techtree account"
    end

    test "stand-in coordinates are described but never offered", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/docs")

      assert visible_text(html) =~ "There is nothing to install from here yet"
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
      assert text =~ "a proposal may be unusable, or may run and change nothing"
    end

    test "the exit codes and the supported variables are the real ones", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/docs")
      text = visible_text(html)

      assert text =~ "TECHTREE_OUTPUT_MODE"
      assert text =~ "TECHTREE_LOG_LEVEL"
      assert text =~ "TECHTREE_ACTIVE_ENGINE_DIGEST"
      assert text =~ "TECHTREE_HOME"

      # The credential variable a Campaign names is not public information.
      refute text =~ "PRIME_API_KEY"
      assert text =~ "Techtree never asks you for the value"
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
           |> element(~s|#copy-docs-install[data-copy-value="uv tool install techtree==0.1.0"]|)
           |> has_element?()

    assert text =~ release.digest
    assert text =~ release.source_revision
    assert text =~ "techtree doctor --climb hello-world-climb@1"
    assert text =~ "techtree climb prepare hello-world-climb@1 --skill path/to/skill"
    assert text =~ "macOS or Linux · Python 3.12, provided by the installer · Docker required"
  end

  defp byte_offset(haystack, needle) do
    {offset, _length} = :binary.match(haystack, needle)
    offset
  end
end
