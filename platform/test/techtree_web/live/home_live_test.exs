defmodule TechtreeWeb.HomeLiveTest do
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

    test "the landing page says what this is and then how to install it", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/")
      text = visible_text(html)

      assert text =~ "Techtree Climb"
      assert text =~ "Test one change to an agent on your own machine"
      assert text =~ "My agent is installing"
      assert text =~ "I’m installing"
      assert text =~ "Give this to your Hermes agent"
    end

    test "the landing page opens on the agent path", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/")

      assert visible_text(html) =~
               "Read the pinned Techtree installation guide at https://techtree.sh/start."

      refute html =~ "hermes plugins install"
      refute html =~ "Prefer installing it yourself?"
    end

    test "the other path is the alternate one, with the pinned plugin under it",
         %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/?install=me")
      text = visible_text(html)

      assert text =~ "Prefer installing it yourself?"
      assert text =~ "Install the exact pinned Hermes plugin shown below."
      assert text =~ "Restart Hermes."
      assert text =~ "Ask: “Set up Techtree and run the Hello World Climb.”"

      assert html =~ "hermes plugins install regents-ai/techtree-hermes --ref"
    end

    test "the landing page stays out of the details and points at the guide", %{conn: conn} do
      {:ok, live, html} = live(conn, ~p"/")

      refute html =~ "uv tool install"
      refute html =~ "Before you start"

      assert live
             |> element(~s|a[href="/start"]|, "The full installation guide")
             |> has_element?()
    end

    test "the landing page says what Hermes is and what a hosted one cannot do yet",
         %{conn: conn} do
      {:ok, live, html} = live(conn, ~p"/")
      text = visible_text(html)

      assert text =~ "Hermes is an open-source agent made by Nous Research."

      assert text =~
               "Nous Portal provides model access, hosted tools, and cloud-hosted Hermes " <>
                 "under one account."

      assert text =~
               "The Nous Portal cloud-hosted path is not yet a separately certified " <>
                 "Techtree execution environment."

      assert live |> element(~s|a[href="https://portal.nousresearch.com/"]|) |> has_element?()
    end

    test "either path calls the introductory Climb a toy demonstration", %{conn: conn} do
      for address <- [~p"/", ~p"/?install=me"] do
        {:ok, _live, html} = live(conn, address)

        assert visible_text(html) =~
                 "A toy introductory demonstration of the mechanism, " <>
                   "not a measure of broad capability.",
               "#{address} drops the qualification"
      end
    end

    test "either path says what is not uploaded and where model calls go", %{conn: conn} do
      for address <- [~p"/", ~p"/?install=me"] do
        {:ok, _live, html} = live(conn, address)
        text = visible_text(html)

        assert text =~
                 "Techtree does not upload your recordings, your results, or the work you submit."

        assert text =~ "sent to the model provider you selected"
      end
    end

    test "the landing page keeps the participant-attested wording", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/")
      text = visible_text(html)

      assert text =~ "signed on the machine that produced it and can be checked there, offline"
      assert text =~ "has not been independently reproduced"
    end

    test "the landing page keeps the deeper pages one link away", %{conn: conn} do
      {:ok, live, _html} = live(conn, ~p"/")

      for path <- ["/climbs", "/protocol", "/proofs/local"] do
        assert live |> element(~s|a[href="#{path}"]|) |> has_element?()
      end
    end

    test "the landing page invents no activity and claims no independent checking",
         %{conn: conn} do
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
  end

  test "the landing page needs no catalog to render", %{conn: conn} do
    {:ok, _live, html} = live(conn, ~p"/")

    assert visible_text(html) =~ "Installation details are not published on this site yet."
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
