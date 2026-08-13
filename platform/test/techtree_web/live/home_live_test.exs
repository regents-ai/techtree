defmodule TechtreeWeb.HomeLiveTest do
  use TechtreeWeb.ConnCase, async: false

  import Phoenix.LiveViewTest

  test "the landing page says what this is and what it asks", %{conn: conn} do
    {:ok, _live, html} = live(conn, ~p"/")

    assert html =~ "Techtree Climb"
    assert html =~ "Controlled trials for agent skills and harnesses."
    assert html =~ "What changed?"
    assert html =~ "What stayed fixed?"
    assert html =~ "Did the score move?"
    assert html =~ "Start on your machine"
    assert html =~ "Browse Climbs"
    assert html =~ "Read the protocol"
  end

  test "the landing page invents no activity and claims no independent checking", %{conn: conn} do
    {:ok, _live, html} = live(conn, ~p"/")

    for fabrication <- [
          "participants",
          "runs completed",
          "leaderboard",
          "trending",
          "join thousands",
          "independently verified",
          "verified by techtree"
        ] do
      refute String.downcase(html) =~ fabrication
    end

    refute html =~ ~r/\d+\s+(participants|teams|runs|submissions)/i
  end

  test "the landing page needs no catalog to render", %{conn: conn} do
    assert {:ok, _live, _html} = live(conn, ~p"/")
  end

  test "every page is reachable from every page", %{conn: conn} do
    for path <- [~p"/", ~p"/start", ~p"/climbs", ~p"/proofs/local", ~p"/protocol"] do
      {:ok, _live, html} = live(conn, path)

      assert html =~ ~s|href="/start"|
      assert html =~ ~s|href="/climbs"|
      assert html =~ ~s|href="/proofs/local"|
      assert html =~ ~s|href="/protocol"|
    end
  end
end
