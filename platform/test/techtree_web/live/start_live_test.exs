defmodule TechtreeWeb.StartLiveTest do
  use TechtreeWeb.ConnCase, async: false

  import Phoenix.LiveViewTest

  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture
  alias TechtreeWeb.ReleaseInfo
  alias TechtreeWeb.StartLive

  describe "with an installable release" do
    setup %{tmp_dir: tmp_dir} do
      bundle = CatalogFixture.copy!(tmp_dir)
      CatalogFixture.rewrite_bootstrap!(bundle, &CatalogFixture.concrete_release/1)
      CatalogFixture.use_bundle(bundle)
      Importer.import!(bundle)
      :ok
    end

    @tag :tmp_dir
    test "one instruction comes first, with the release-derived setup paths after it", %{
      conn: conn
    } do
      {:ok, live, html} = live(conn, ~p"/start")
      release = ReleaseInfo.current()
      instruction = StartLive.instruction()

      expected_cli =
        [
          Enum.join(release.install_argv, " "),
          "techtree forge inspect-skill path/to/your-skill",
          "# Then plan with a provider and model you choose:",
          "techtree forge plan --help",
          "# Every review waits for your answer."
        ]
        |> Enum.join("\n")

      expected_hermes =
        [
          Enum.join(release.plugin_install_argv, " "),
          Enum.join(release.plugin_doctor_argv, " "),
          "# In a fresh Hermes session, enter:",
          "/techtree setup"
        ]
        |> Enum.join("\n")

      escape = fn text -> text |> Phoenix.HTML.html_escape() |> Phoenix.HTML.safe_to_string() end

      assert instruction =~ url(~p"/skill.md")
      assert instruction =~ "Ask me where my Skill is."
      assert instruction =~ "Never approve anything for me."
      assert html =~ ~s|data-copy-value="#{escape.(instruction)}"|
      assert html =~ ~s|data-copy-value="#{escape.(expected_cli)}"|
      assert html =~ ~s|data-copy-value="#{escape.(expected_hermes)}"|

      expected_example =
        [
          Enum.join(release.install_argv, " "),
          "techtree doctor --climb #{release.introductory_reference}",
          "techtree skill starter",
          "# Prepare with the Skill it placed, then run the start command it prints:",
          "techtree climb prepare #{release.introductory_reference} --skill path/to/skill"
        ]
        |> Enum.join("\n")

      assert html =~ ~s|data-copy-value="#{escape.(expected_example)}"|

      for id <- [
            "copy-start-example",
            "copy-start-instruction",
            "copy-setup-cli",
            "copy-setup-hermes",
            "copy-start-repository"
          ] do
        assert has_element?(live, "##{id}", "Copy")
        assert has_element?(live, "##{id} + [data-copy-status][role=status][aria-live=polite]")
      end

      [instruction_at, cli_at] =
        Enum.map(
          ["copy-start-instruction", "copy-setup-cli"],
          &(:binary.match(html, &1) |> elem(0))
        )

      assert instruction_at < cli_at
      assert has_element?(live, "#setup-direct", "Or set it up yourself")
    end

    @tag :tmp_dir
    test "query parameters do not create alternate installation paths", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/start?install=me")

      assert html =~ "copy-start-instruction"
      refute html =~ "Prefer installing it yourself?"
    end
  end

  # A reader pays for the example's model calls on their own key, so what the
  # page tells them — the model, the key, the tasks and the limits — has to be
  # what the Climb's Campaign declares, not words that can drift from it.
  @tag :tmp_dir
  test "the example states the model, key, tasks and limits its Campaign declares", %{
    conn: conn,
    tmp_dir: tmp_dir
  } do
    bundle = CatalogFixture.copy!(tmp_dir)
    CatalogFixture.rewrite_bootstrap!(bundle, &CatalogFixture.concrete_release/1)

    CatalogFixture.rewrite_campaign!(bundle, fn campaign ->
      campaign
      |> put_in(["agents", "subject", "model", "model_id"], "example/other-model")
      |> put_in(["agents", "subject", "model", "credential_env"], "OTHER_PROVIDER_KEY")
      |> put_in(["budgets", "maximum_model_calls"], 7)
      |> put_in(["budgets", "maximum_input_tokens"], 1_234_567)
      |> put_in(["budgets", "maximum_output_tokens"], 8_000)
      |> put_in(["taskset", "selection", "num_tasks"], 5)
      |> update_in(["taskset", "membership", "ordered_task_hashes"], &Enum.take(&1, 5))
    end)

    CatalogFixture.use_bundle(bundle)
    Importer.import!(bundle)

    {:ok, _live, html} = live(conn, ~p"/start")
    text = visible_text(html)

    assert text =~ "example/other-model"
    assert text =~ "OTHER_PROVIDER_KEY"
    assert text =~ "after 7 calls, 1,234,567 input tokens or 8,000 output tokens"
    assert text =~ "With 5 tasks, a run can make up to 70 model calls"
    refute text =~ "qwen/qwen3.7-flash"
    refute text =~ "PRIME_API_KEY"
  end

  test "a channel with nothing to install offers no instruction and no command", %{conn: conn} do
    CatalogFixture.use_bundle(CatalogFixture.root())
    Importer.import!(CatalogFixture.root())

    {:ok, live, html} = live(conn, ~p"/start")

    assert has_element?(
             live,
             ".setup-unavailable",
             "No concrete release is available to install yet."
           )

    for id <- [
          "copy-start-example",
          "copy-start-instruction",
          "copy-setup-cli",
          "copy-setup-hermes",
          "copy-start-repository"
        ] do
      refute html =~ id
    end
  end
end
