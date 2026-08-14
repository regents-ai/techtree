defmodule TechtreeWeb.StartLiveTest do
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

    test "the agent path is the one open by default", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/start")

      assert html =~ "hermes plugins install regents-labs/techtree-hermes --ref"
      assert html =~ "hermes plugins doctor techtree --ci"
      assert html =~ "Set up Techtree and run the Hello World Climb."

      refute html =~ "uv tool install"
      refute html =~ "techtree setup"
    end

    test "the terminal path is the one the address can ask for", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/start?install=me")

      assert html =~ "uv tool install techtree==0.0.0-placeholder"
      assert html =~ "techtree setup"
      assert html =~ "techtree climb show hello-world-climb@1"

      refute html =~ "hermes plugins install"
    end

    test "an address that names no path opens the agent one", %{conn: conn} do
      {:ok, _live, html} = live(conn, "/start?install=whatever")

      assert html =~ "hermes plugins install"
      refute html =~ "uv tool install"
    end

    test "the switcher swaps which path is in front", %{conn: conn} do
      {:ok, live, _html} = live(conn, ~p"/start")

      terminal = live |> element(~s|a[href="/start?install=me"]|) |> render_click()

      assert terminal =~ "uv tool install"
      refute terminal =~ "hermes plugins install"

      agent = live |> element(~s|a[href="/start?install=agent"]|) |> render_click()

      assert agent =~ "hermes plugins install"
      refute agent =~ "uv tool install"
    end

    test "the switcher is an ordinary link, so it works without a live connection",
         %{conn: conn} do
      html = conn |> get(~p"/start") |> html_response(200)

      assert html =~ ~s|href="/start?install=me"|
      assert html =~ ~s|href="/start?install=agent"|

      switched = conn |> get(~p"/start?install=me") |> html_response(200)

      assert switched =~ "uv tool install"
    end

    test "the switcher marks the path that is open", %{conn: conn} do
      {:ok, live, _html} = live(conn, ~p"/start")

      assert live |> element(~s|a[href="/start?install=agent"][aria-current]|) |> has_element?()
      refute live |> element(~s|a[href="/start?install=me"][aria-current]|) |> has_element?()
    end

    test "either path says what the introductory Climb is and is not", %{conn: conn} do
      for address <- [~p"/start", ~p"/start?install=me"] do
        {:ok, live, html} = live(conn, address)

        assert html =~
                 "A toy introductory demonstration of the mechanism, " <>
                   "not a measure of broad capability."

        assert live |> element(~s|a[href="/climbs/hello-world-climb"]|) |> has_element?()
      end
    end

    test "either path says what the machine needs and where the model calls go",
         %{conn: conn} do
      for address <- [~p"/start", ~p"/start?install=me"] do
        {:ok, _live, html} = live(conn, address)
        text = visible_text(html)

        assert text =~ "Docker running"
        assert text =~ "macOS or Linux"
        assert text =~ "Hermes 0.19.0 or newer"
        assert text =~ "a key from your model provider"
        assert text =~ "The agent under test makes real model calls"
      end
    end

    test "the placeholder release is labelled where the commands are shown", %{conn: conn} do
      for address <- [~p"/start", ~p"/start?install=me"] do
        {:ok, _live, html} = live(conn, address)

        assert html =~ "not a real release yet"
        assert html =~ "They install nothing."
      end
    end

    test "no command is presented as a line to be run by the site", %{conn: conn} do
      for address <- [~p"/start", ~p"/start?install=me"] do
        {:ok, _live, html} = live(conn, address)

        refute html =~ "curl"
        refute html =~ "| sh"
        refute html =~ "sudo"
      end
    end
  end

  describe "with nothing published" do
    setup do
      CatalogFixture.use_bundle(CatalogFixture.root())
    end

    test "the page says so calmly and shows no invented commands", %{conn: conn} do
      for address <- [~p"/start", ~p"/start?install=me"] do
        {:ok, _live, html} = live(conn, address)

        assert html =~ "Installation details are not published on this site yet."
        refute html =~ "uv tool install"
        refute html =~ "hermes plugins install"
      end
    end
  end
end
