defmodule TechtreeWeb.ProofsLiveTest do
  @moduledoc """
  The secondary verifier reference states both sides of the proof boundary.
  """

  use TechtreeWeb.ConnCase, async: false

  import Phoenix.LiveViewTest

  test "balances verified evidence with what remains unproven", %{conn: conn} do
    {:ok, live, html} = live(conn, ~p"/proofs")
    text = visible_text(html)

    assert text =~ "How verification works"
    assert text =~ "What Techtree verifies"
    assert text =~ "What remains unproven"
    assert text =~ "Internally checkable evidence"
    assert text =~ "Verification is not observation"
    assert text =~ "The site did not witness the execution."
    assert text =~ "not independently attested"
    assert text =~ "does not establish generalization beyond the Climb"
    assert text =~ "Nobody else reproduced it"
    assert has_element?(live, ~s|a[href="/results"]|, "Browse published proofs")
  end

  test "keeps the exact checks in a collapsed reference", %{conn: conn} do
    {:ok, live, _html} = live(conn, ~p"/proofs")
    count = Techtree.Network.Bundle.check_count()

    assert has_element?(live, "details#verifier-reference:not([open])")

    assert has_element?(
             live,
             "details#verifier-reference summary",
             "Verifier reference: all #{count} checks"
           )

    for {_name, words} <- Techtree.Network.Bundle.checks() do
      assert has_element?(live, "#verifier-reference .checks li", words)
    end
  end

  test "offers the offline verifier without obsolete release promises", %{conn: conn} do
    {:ok, live, html} = live(conn, ~p"/proofs")
    text = visible_text(html)

    assert has_element?(
             live,
             ~s|#copy-proof-verify[data-copy-value="techtree proof verify path/to/result-bundle"]|
           )

    refute text =~ "arrives in a later release"
    refute text =~ "USDC"
    refute has_element?(live, "#proof-evidence-graph")
  end
end
