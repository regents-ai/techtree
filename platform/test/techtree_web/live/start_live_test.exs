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

    test "the commands are the ones the release publishes", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/start")

      assert html =~ "uv tool install techtree==0.0.0-placeholder"
      assert html =~ "hermes plugins install regents-labs/techtree-hermes --ref"
      assert html =~ "hermes plugins doctor techtree --ci"
      assert html =~ "techtree setup"
      assert html =~ "techtree climb list"
      assert html =~ "techtree climb show hello-world-climb@1"
      assert html =~ "Set up Techtree and run the Hello World Climb."
    end

    test "the introductory Climb is described as a toy demonstration", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/start")

      assert html =~
               "A toy introductory demonstration of the mechanism, not a measure of broad capability."
    end

    test "the placeholder release is labelled where the commands are shown", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/start")

      assert html =~ "not a real release yet"
      assert html =~ "They install nothing."
    end

    test "the page says what the machine must have", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/start")

      assert html =~ "Docker"
      assert html =~ "model provider"
      assert html =~ "0.19.0"
      assert html =~ "macOS or Linux"
    end

    test "the introductory Climb is linked", %{conn: conn} do
      {:ok, live, _html} = live(conn, ~p"/start")

      assert live |> element(~s|a[href="/climbs/hello-world-climb"]|) |> has_element?()
    end

    test "no command is presented as a line to be run by the site", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/start")

      refute html =~ "curl"
      refute html =~ "| sh"
      refute html =~ "sudo"
    end
  end

  describe "with nothing published" do
    setup do
      CatalogFixture.use_bundle(CatalogFixture.root())
    end

    test "the page says so calmly and shows no invented commands", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/start")

      assert html =~ "Installation details are not published on this site yet."
      refute html =~ "uv tool install"
      refute html =~ "hermes plugins install"
    end
  end
end
