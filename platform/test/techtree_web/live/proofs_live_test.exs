defmodule TechtreeWeb.ProofsLiveTest do
  @moduledoc """
  "View a proof" is the promise this page has to keep honestly. Everything it
  shows is a coordinate the served release publishes; everything a run would
  add is named as absent rather than drawn.
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

    test "the page says plainly that no participant result is published", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/proofs")
      text = visible_text(html)

      assert text =~ "No participant result is published here"
      assert text =~ "This release publishes nothing and receives nothing."
      assert text =~ "arrives in a later release"
    end

    test "every coordinate it shows is one the release publishes", %{conn: conn} do
      {:ok, live, html} = live(conn, ~p"/proofs")
      text = visible_text(html)

      assert has_element?(live, "#proof-evidence-graph")
      assert text =~ CatalogFixture.campaign_digest()
      assert text =~ "36 tasks, fixed before either run"
      assert text =~ "hermes-agent 0.19.0"
      assert text =~ "prime · qwen/qwen3.7-flash"
      assert text =~ "44 model calls"
    end

    test "the changed artifact is the Skill, at the fingerprint the release pins",
         %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/proofs")
      text = visible_text(html)

      assert text =~ "One Skill, mounted in the candidate and absent from the baseline."
      assert text =~ "Starts from hello-world-starter-v1"
      assert text =~ Techtree.Release.StarterSkill.tree_digest()
    end

    test "the score is a band, and the task counts are absent rather than invented",
         %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/proofs")
      text = visible_text(html)

      # The band lives on the Climb and docs pages; this page draws no numbers
      # at all for what only a run can carry (founder ruling 2026-08-26).
      assert text =~ "Scores, every task’s outcome, and a signed bundle."
      refute text =~ ~r/\b\d+\s+(wins|losses|ties)\b/i
      refute text =~ ~r/\b\d{1,3}\s*(\/|out of)\s*36\b/
    end

    test "the reader is told how to check a bundle they hold, offline", %{conn: conn} do
      {:ok, live, html} = live(conn, ~p"/proofs")

      assert visible_text(html) =~ "check it on their own machine"

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

  test "with nothing imported the page says there are no coordinates", %{conn: conn} do
    CatalogFixture.use_bundle(CatalogFixture.root())

    {:ok, _live, html} = live(conn, ~p"/proofs")
    text = visible_text(html)

    assert text =~ "No campaign is published on this channel"
    assert text =~ "No participant result is published here"
  end
end
