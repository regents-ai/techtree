defmodule TechtreeWeb.ProofsLiveTest do
  @moduledoc """
  The Verify page explains how a Result is made and states both what a check
  establishes and what it cannot.
  """

  use TechtreeWeb.ConnCase, async: false

  import Phoenix.LiveViewTest

  test "balances what a check tells you with what it can't", %{conn: conn} do
    {:ok, live, html} = live(conn, ~p"/proofs")
    text = visible_text(html)

    assert text =~ "Check a Result yourself"
    assert text =~ "What a check tells you"
    assert text =~ "What a check can’t tell you"
    assert text =~ "Techtree did not watch the run happen."
    assert text =~ "not that the computer behind it was honest"
    assert text =~ "doesn’t mean better at everything"
    assert text =~ "Only a separate rerun shows that it repeats."
    assert text =~ "Why it matters"
    assert has_element?(live, ~s|a[href="/results"]|, "Browse Results")
  end

  test "names who runs and scores the tasks and shows every check", %{conn: conn} do
    {:ok, live, _html} = live(conn, ~p"/proofs")
    count = Techtree.Network.Bundle.check_count()

    assert has_element?(live, "#how-made h2", "How a Result is made")
    assert has_element?(live, "#local-results", "The Skill is the only difference.")

    assert has_element?(
             live,
             ~s|#how-made a[href="https://github.com/PrimeIntellect-ai/verifiers"]|,
             "Read Prime Intellect’s Verifiers"
           )

    assert has_element?(
             live,
             ~s|#how-made a[href="https://github.com/NousResearch/hermes-agent"]|
           )

    assert has_element?(live, "#verifier-checks summary", "#{count} checks")

    for {_name, words} <- Techtree.Network.Bundle.checks() do
      assert has_element?(live, "#verifier-checks .checks li", words)
    end
  end

  test "offers the offline check without obsolete release promises", %{conn: conn} do
    {:ok, live, html} = live(conn, ~p"/proofs")
    text = visible_text(html)

    assert copied_text(html, "copy-proof-verify") ==
             "regents techtree proof verify path/to/result-bundle"

    refute text =~ "arrives in a later release"
    refute text =~ "USDC"
    refute has_element?(live, "#proof-evidence-graph")
    assert has_element?(live, ~s|a[href="/docs#verify"]|)
    assert has_element?(live, ~s|a[href="/docs#method"]|, "Docs")
    assert text =~ "copyable as Markdown to your agent"
  end
end
