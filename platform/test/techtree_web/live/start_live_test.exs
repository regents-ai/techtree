defmodule TechtreeWeb.StartLiveTest do
  use TechtreeWeb.ConnCase, async: false

  import Phoenix.LiveViewTest

  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture
  alias TechtreeWeb.ReleaseInfo

  @instruction "Set up Techtree and run the Hello World Climb."
  @setup_paths "Choose the Techtree CLI or Hermes plugin path below."

  setup %{tmp_dir: tmp_dir} do
    bundle = CatalogFixture.copy!(tmp_dir)
    CatalogFixture.rewrite_bootstrap!(bundle, &CatalogFixture.concrete_release/1)
    CatalogFixture.use_bundle(bundle)
    Importer.import!(bundle)
    :ok
  end

  @tag :tmp_dir
  test "Start presents both release-derived setup paths in one copyable block", %{conn: conn} do
    {:ok, live, html} = live(conn, ~p"/start")
    release = ReleaseInfo.current()

    expected =
      [
        "# #{@instruction}",
        "# CLI",
        Enum.join(release.install_argv, " "),
        "techtree doctor --climb #{release.introductory_reference}",
        "# Hermes plugin",
        Enum.join(release.plugin_install_argv, " "),
        Enum.join(release.plugin_doctor_argv, " "),
        "# In a fresh Hermes session, enter:",
        "/techtree setup",
        "# Follow Doctor's exact next action. Ask before starting paid model inference."
      ]
      |> Enum.join("\n")

    escaped_expected = expected |> Phoenix.HTML.html_escape() |> Phoenix.HTML.safe_to_string()

    assert visible_text(html) =~ @instruction
    assert visible_text(html) =~ @setup_paths
    assert has_element?(live, "#copy-setup-instruction", "Copy")
    assert html =~ ~s|data-copy-value="#{escaped_expected}"|

    refute html =~ "My agent is installing"
    refute html =~ "I’m installing"
    assert html =~ "hermes plugins install"
    assert html =~ "uv tool install"
    assert html =~ "/techtree setup"
  end

  @tag :tmp_dir
  test "query parameters do not create alternate installation paths", %{conn: conn} do
    {:ok, _live, html} = live(conn, ~p"/start?install=me")

    assert visible_text(html) =~ @instruction
    assert visible_text(html) =~ @setup_paths
    refute html =~ "Prefer installing it yourself?"
  end
end
