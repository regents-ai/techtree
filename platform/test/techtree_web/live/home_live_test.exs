defmodule TechtreeWeb.HomeLiveTest do
  use TechtreeWeb.ConnCase, async: false

  import Phoenix.LiveViewTest

  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture
  alias TechtreeWeb.ReleaseInfo

  describe "with the active catalog imported" do
    setup do
      CatalogFixture.use_bundle(CatalogFixture.root())
      Importer.import!(CatalogFixture.root())
      :ok
    end

    test "the hero makes one promise before introducing the machinery", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/")
      text = visible_text(html)

      assert text =~ "Improve a Skill. Prove it worked."

      assert text =~
               "Run a controlled baseline and candidate on your machine. Techtree keeps the " <>
                 "taskset, model, harness, tools, and budget fixed, then signs the result " <>
                 "so another participant can verify or reproduce it."

      for concept <- [
            "CampaignSpec",
            "TasksetValidationReceipt",
            "manifest",
            "receipt schema",
            "Fabric",
            "Relay"
          ] do
        refute hero_text(html) =~ concept
      end
    end

    test "installation is the sole primary action", %{conn: conn} do
      {:ok, live, html} = live(conn, ~p"/")

      assert live
             |> element(~s|a.button--primary[href="/docs#install"]|, "Install Techtree")
             |> has_element?()

      assert live
             |> element(~s|a.text-link[href="/proofs"]|, "View a verified run")
             |> has_element?()

      assert length(Regex.scan(~r/button--primary/, html)) == 1
      refute html =~ "My agent is installing"
      refute html =~ "I’m installing"
    end

    test "the masthead has exactly the three product destinations", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/")

      assert nav_links(html) == [
               {"https://github.com/regents-ai", "GitHub"},
               {"/docs", "Docs"},
               {"/proofs", "View a proof"}
             ]
    end

    test "the graph exposes only artifacts that actually exist", %{conn: conn} do
      {:ok, live, _html} = live(conn, ~p"/")
      graph = live |> element("#home-evidence-graph") |> render()
      text = visible_text(graph)

      assert text =~ "Campaign"
      assert text =~ "Baseline"
      assert text =~ "Candidate"
      assert text =~ "Task validation"
      assert text =~ CatalogFixture.campaign_digest()
      assert text =~ "36 tasks validated"
      assert text =~ "Declared; no public run receipt"
      refute text =~ "Signed proof"
      refute text =~ "Independent reproduction"
      refute text =~ ~r/\+?\d+(\.\d+)?%/
    end

    test "a placeholder release never becomes an executable installer", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/")
      text = visible_text(html)

      assert text =~ "This channel has placeholder coordinates."
      refute html =~ "techtree==0.0.0-placeholder"
      refute html =~ "0000000000000000000000000000000000000000"
    end

    test "the homepage has only its four requested content regions", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/")

      assert html =~ ~s|class="hero"|
      assert html =~ ~s|class="home-section process"|
      assert html =~ ~s|class="home-section featured"|
      assert html =~ ~s|class="home-section trust"|

      for absent <- ["Sign in", "Leaderboard", "Pricing", "Dashboard", "Marketplace"] do
        refute html =~ absent
      end
    end

    test "the trust boundary names local data, provider calls, and proof limits", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/")
      text = visible_text(html)

      assert text =~
               "Techtree does not upload your recordings, result bundle, or submitted Skill."

      assert text =~ "calls to the model provider you selected"
      assert text =~ "A signed local proof establishes internal consistency and authorship."
      assert text =~ "only when another participant runs and attests to it"
    end
  end

  @tag :tmp_dir
  test "a concrete active release supplies the one copied install command", %{
    conn: conn,
    tmp_dir: tmp_dir
  } do
    bundle = CatalogFixture.copy!(tmp_dir)
    CatalogFixture.rewrite_bootstrap!(bundle, &CatalogFixture.concrete_release/1)
    CatalogFixture.use_bundle(bundle)
    Importer.import!(bundle)

    release = ReleaseInfo.current()
    {:ok, live, html} = live(conn, ~p"/")

    assert release.installable?

    assert live
           |> element(~s|#copy-home-install[data-copy-value="uv tool install techtree==0.1.0"]|)
           |> has_element?()

    assert visible_text(html) =~ "Python 3.12+"
    assert visible_text(html) =~ "Docker required"
    assert visible_text(html) =~ "Hermes 0.20.1+ optional"
    refute html =~ "techtree up"
  end

  test "the homepage renders without a catalog or release", %{conn: conn} do
    CatalogFixture.use_bundle(CatalogFixture.root())

    {:ok, _live, html} = live(conn, ~p"/")

    assert visible_text(html) =~ "No install release is active on this channel."
    refute html =~ "home-evidence-graph"
    refute html =~ "home-section featured"
  end

  defp hero_text(html) do
    [copy] = Regex.run(~r/<div class="hero__copy".*?<\/div>/s, html)
    visible_text(copy)
  end

  defp nav_links(html) do
    [nav] = Regex.run(~r/<nav class="masthead__nav".*?<\/nav>/s, html)

    Regex.scan(~r/<a[^>]*href="([^"]+)"[^>]*>(.*?)<\/a>/s, nav, capture: :all_but_first)
    |> Enum.map(fn [href, label] -> {href, visible_text(label) |> String.trim()} end)
  end
end
