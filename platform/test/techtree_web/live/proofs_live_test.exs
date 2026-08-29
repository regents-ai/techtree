defmodule TechtreeWeb.ProofsLiveTest do
  @moduledoc """
  Proofs names the exact checks and the boundary of participant attestation.
  """

  use TechtreeWeb.ConnCase, async: false

  import Phoenix.LiveViewTest

  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture

  describe "with a release being served" do
    setup do
      CatalogFixture.use_bundle(CatalogFixture.root())
      Importer.import!(CatalogFixture.root())
      :ok
    end

    test "lists every check the server applies", %{conn: conn} do
      {:ok, live, html} = live(conn, ~p"/proofs")
      text = visible_text(html)

      refute has_element?(live, "#proof-evidence-graph")

      for {_name, sentence} <- Techtree.Network.Bundle.checks() do
        assert text =~ sentence
      end
    end

    test "states the participant-attestation boundary once", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/proofs")
      text = visible_text(html)

      assert text =~ "Verification is not observation."
      assert text =~ "internally consistent and signed by the participant-controlled key"
      assert text =~ "does not prove the machine behaved honestly"
      assert text =~ "that anyone reproduced it"
      refute text =~ "Example Baseline vs. Instructional Skill"
      refute text =~ "The comparison"
    end

    test "the reader can check a bundle offline", %{conn: conn} do
      {:ok, live, html} = live(conn, ~p"/proofs")

      assert visible_text(html) =~ "Verification makes no model request and needs no network."

      assert live
             |> element(
               ~s|#copy-proof-verify[data-copy-value="techtree proof verify path/to/result-bundle"]|
             )
             |> has_element?()
    end

    test "the page claims no witness it does not have", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/proofs")
      text = String.downcase(visible_text(html))

      assert text =~ "participant-attested"
      refute text =~ "verified by techtree"
      refute text =~ "independently verified"
      refute text =~ "trustless"
      refute text =~ "download"
    end
  end

  test "the proof boundary does not depend on the catalog", %{conn: conn} do
    CatalogFixture.use_bundle(CatalogFixture.root())

    {:ok, _live, html} = live(conn, ~p"/proofs")
    text = visible_text(html)

    assert text =~ "What verification establishes"
    assert text =~ "Verification is not observation."
  end
end
