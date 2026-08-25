defmodule TechtreeWeb.ProofsLiveTest do
  use TechtreeWeb.ConnCase, async: false

  import Phoenix.LiveViewTest

  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture

  test "the proof index does not turn private or certification evidence into a result", %{
    conn: conn
  } do
    CatalogFixture.use_bundle(CatalogFixture.root())
    Importer.import!(CatalogFixture.root())

    {:ok, live, html} = live(conn, ~p"/proofs")
    text = visible_text(html)

    assert text =~ "No proof is curated for public release yet."
    assert text =~ "Local proofs never upload automatically."
    assert text =~ "no participant proof with publication authorization"

    assert live
           |> element(
             ~s|#copy-proof-index-verify[data-copy-value="techtree proof verify path/to/result-bundle"]|
           )
           |> has_element?()

    refute text =~ "verified by Techtree"
    refute text =~ "independently verified"
  end

  test "an arbitrary digest never resolves as a public proof", %{conn: conn} do
    digest = "sha256:" <> String.duplicate("a", 64)

    assert_error_sent 404, fn -> live(conn, "/proofs/#{digest}") end
  end
end
