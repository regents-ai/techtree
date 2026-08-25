defmodule TechtreeWeb.DocsLiveTest do
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

    test "the quickstart comes before the conceptual reference", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/docs")
      text = visible_text(html)

      assert text =~ "Get to a controlled first run."
      assert text =~ "What leaves my machine?"
      assert text =~ "Run a real campaign"
      assert text =~ "Campaigns"
      assert text =~ "Baseline and candidate"
      assert text =~ "Proofs and reproduction"
      assert text =~ "Harness support"
      assert text =~ "Threat model"

      assert byte_offset(html, ~s|id="quickstart"|) < byte_offset(html, ~s|id="campaigns"|)
    end

    test "placeholder coordinates are described but never offered", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/docs")

      assert visible_text(html) =~ "Installation is not published on this channel"
      refute html =~ "techtree==0.0.0-placeholder"
      refute html =~ String.duplicate("0", 40)
    end

    test "the reference names only commands that actually ship", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/docs")
      text = visible_text(html)

      for command <- [
            "setup",
            "doctor",
            "climb",
            "skill",
            "run",
            "engine",
            "proof",
            "release",
            "uplift"
          ] do
        assert text =~ command
      end

      refute text =~ "techtree up"
      refute text =~ "techtree harness list"
      refute text =~ "v0.2"
    end
  end

  @tag :tmp_dir
  test "a concrete release drives install, release, and copy metadata", %{
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
  end

  defp byte_offset(haystack, needle) do
    {offset, _length} = :binary.match(haystack, needle)
    offset
  end
end
