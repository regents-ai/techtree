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

    test "the example result is the certified report, drawn from the served file", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/proofs")
      text = visible_text(html)

      # Founder ruling 2026-08-26: this page shows the real certified example,
      # exact counts included — a single curated exception to the band rule.
      # Every number must equal the signed report the site ships; the numbers
      # are recomputed here from that same file, never written into this test.
      example = TechtreeWeb.ExampleResult.load()

      assert example, "the example report is missing from priv/examples"
      assert text =~ "Example Baseline vs. Instructional Skill"
      assert text =~ "#{example.baseline_total} of #{example.tasks} tasks"
      assert text =~ "#{example.candidate_total} of #{example.tasks} tasks"
      assert text =~ "#{example.wins} wins · #{example.ties} ties · #{example.losses} losses"
      assert text =~ example.file_digest
      assert text =~ example.run_id
      assert text =~ "Participant-attested"
      assert text =~ "arrives in a later release"
    end

    test "the example is drawn only for the campaign it measured", %{conn: conn} do
      example = TechtreeWeb.ExampleResult.load()

      assert example.campaign_spec_digest == CatalogFixture.campaign_digest(),
             "the shipped example measures a campaign this channel does not serve"

      assert TechtreeWeb.ExampleResult.for_campaign("sha256:" <> String.duplicate("0", 64)) ==
               nil

      {:ok, _live, html} = live(conn, ~p"/proofs")
      assert visible_text(html) =~ example.campaign_spec_digest
      refute is_nil(conn)
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

    test "every count on the page comes from the served report", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/proofs")
      text = visible_text(html)
      example = TechtreeWeb.ExampleResult.load()

      assert text =~ "Scores, every task’s outcome, and a signed bundle."

      # The only win/tie/loss figures allowed are the report's own.
      for [count, kind] <-
            Regex.scan(~r/\b(\d+)\s+(wins|ties|losses)\b/i, text, capture: :all_but_first) do
        assert String.to_integer(count) == Map.fetch!(example, String.to_existing_atom(kind)),
               "the page says #{count} #{kind}, the signed report does not"
      end
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
