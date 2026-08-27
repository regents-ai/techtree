defmodule TechtreeWeb.NetworkLiveTest do
  @moduledoc """
  What the two pages of the run log show, and what they refuse to show.

  Several of these tests are about absences, and the absences are the point. A
  log that grew a position number, a sort control, or a sentence somebody typed
  would still render; it would just no longer be the thing that was designed.

  So the order is asserted against a deliberately unhelpful set of entries: three
  runs published one after another, each with a worse result than the one before
  it. A page that ordered by result would show them in exactly the opposite
  order to a page that logs, which is what makes the assertion mean something.
  """

  use TechtreeWeb.ConnCase, async: false

  import Phoenix.LiveViewTest

  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture
  alias Techtree.Network.Ingest
  alias Techtree.NetworkFixture

  setup do
    CatalogFixture.use_bundle(CatalogFixture.root())
    Importer.import!(CatalogFixture.root())
    :ok
  end

  describe "with nothing published" do
    test "the log says so rather than showing an empty frame", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/network")

      assert visible_text(html) =~ "Nobody has published a run yet"
    end

    test "a run nobody published is not found", %{conn: conn} do
      assert_error_sent 404, fn ->
        live(conn, "/network/sha256:#{String.duplicate("a", 64)}")
      end
    end
  end

  describe "the log" do
    setup :publish_a_run

    test "shows when, the agent, the model, the counts, the difference and the grade",
         %{conn: conn, entry: entry} do
      {:ok, _live, html} = live(conn, ~p"/network")
      text = visible_text(html)

      assert text =~ "hermes-agent 0.19.0"
      assert text =~ "qwen/qwen3.7-flash"
      assert text =~ "#{entry.wins} better"
      assert text =~ "#{entry.ties} same"
      assert text =~ "#{entry.losses} worse"
      assert text =~ "+0.639"
      assert text =~ "P1"
      assert text =~ Calendar.strftime(entry.inserted_at, "%Y-%m-%d")
    end

    test "names the publisher by a short form of their key's fingerprint",
         %{conn: conn, entry: entry} do
      {:ok, _live, html} = live(conn, ~p"/network")
      text = visible_text(html)

      "sha256:" <> hex = entry.executor_key_id

      assert text =~ "sha256:" <> String.slice(hex, 0, 12)
      refute text =~ entry.executor_key_id
    end

    test "says what this site checked and what it did not", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/network")
      text = visible_text(html)

      assert text =~ "internally consistent and signed by the key it names"
      assert text =~ "not a claim that the run happened"
      assert text =~ "did not watch it and has not repeated it"
    end

    test "carries no rank, no position and nothing to reorder it by", %{conn: conn} do
      {:ok, live, html} = live(conn, ~p"/network")
      text = html |> visible_text() |> String.downcase()

      for word <- ["rank", "leaderboard", "position", "sort by", "#1", "top "] do
        refute text =~ word, "the log says #{inspect(word)}"
      end

      refute live |> element("select") |> has_element?()
      refute live |> element("[phx-click]") |> has_element?()
      refute html =~ "<form"
    end
  end

  describe "the log with several entries" do
    setup :publish_several_runs

    test "is in arrival order, newest first, and not in order of result",
         %{conn: conn, entries: entries} do
      arrived = Enum.map(entries, & &1.bundle_digest)

      # The setup is only worth anything if the results really do run downhill.
      assert Enum.map(entries, & &1.wins) == [23, 14, 7]

      {:ok, _live, html} = live(conn, ~p"/network")

      shown =
        ~r|/network/(sha256:[0-9a-f]{64})|
        |> Regex.scan(html, capture: :all_but_first)
        |> List.flatten()
        |> Enum.uniq()

      assert shown == Enum.reverse(arrived)

      by_result = entries |> Enum.sort_by(& &1.wins, :desc) |> Enum.map(& &1.bundle_digest)

      refute shown == by_result
    end

    test "a withdrawn entry leaves the log entirely", %{conn: conn, entries: entries} do
      withdrawn = Enum.at(entries, 1)
      Ingest.withdraw(withdrawn, :requested_by_publisher)

      {:ok, _live, html} = live(conn, ~p"/network")

      refute html =~ withdrawn.bundle_digest

      for kept <- List.delete(entries, withdrawn) do
        assert html =~ kept.bundle_digest
      end
    end
  end

  describe "one entry's own page" do
    setup :publish_a_run

    test "shows every task with both sides' rewards and the difference",
         %{conn: conn, entry: entry} do
      {:ok, _live, html} = live(conn, "/network/#{entry.bundle_digest}")
      text = visible_text(html)

      assert text =~ "36 tasks"

      for task <- entry.task_deltas do
        assert html =~ task["task_hash"]
      end

      first = hd(entry.task_deltas)

      assert text =~
               "Without the Skill #{first["baseline_reward"]} With the Skill " <>
                 "#{first["candidate_reward"]} Change +1.0"
    end

    test "shows the coordinates the run pins, from the campaign this site publishes",
         %{conn: conn, entry: entry} do
      {:ok, _live, html} = live(conn, "/network/#{entry.bundle_digest}")
      text = visible_text(html)

      assert text =~ "36 tasks, fixed before either run"
      assert text =~ "44 model calls"
      assert text =~ entry.campaign_spec_digest
      assert text =~ entry.data_policy_digest
      assert text =~ entry.run_id
      assert html =~ ~s|href="/campaigns/hello-world-climb"|
    end

    test "lists the checks that ran, how many passed, and what none of them prove",
         %{conn: conn, entry: entry} do
      {:ok, _live, html} = live(conn, "/network/#{entry.bundle_digest}")
      text = visible_text(html)

      assert text =~ "8 of 8 passed"

      for {_name, sentence} <- Techtree.Network.Bundle.checks() do
        assert text =~ sentence
      end

      assert text =~ "None of them is a claim that the run happened"
      assert text =~ "did not watch it and has not repeated it"
    end

    test "links to the exact bytes the site was given", %{conn: conn, entry: entry} do
      {:ok, _live, html} = live(conn, "/network/#{entry.bundle_digest}")

      assert html =~ ~s|href="/api/v1/submissions/#{entry.bundle_digest}"|
    end

    test "a withdrawn entry says so and shows nothing else", %{conn: conn, entry: entry} do
      Ingest.withdraw(entry, :requested_by_publisher)

      {:ok, _live, html} = live(conn, "/network/#{entry.bundle_digest}")
      text = visible_text(html)

      assert text =~ "This run was withdrawn"

      refute text =~ "qwen/qwen3.7-flash"
      refute text =~ entry.run_id
      refute text =~ entry.executor_key_id
      refute html =~ hd(entry.task_deltas)["task_hash"]
      refute text =~ "8 of 8 passed"
    end
  end

  defp publish_a_run(_context) do
    {:ok, entry, :recorded} = Ingest.accept(NetworkFixture.submission())
    {:ok, entry: entry}
  end

  # Three entries whose results run downhill as they arrive, so that a page
  # ordered by result would show them in exactly the opposite order.
  defp publish_several_runs(_context) do
    entries =
      for dropped <- [0, 10, 20] do
        {:ok, entry, :recorded} = Ingest.accept(NetworkFixture.submission(worse_by(dropped)))
        entry
      end

    {:ok, entries: entries}
  end

  # The same run with the first `dropped` tasks scoring nothing on the candidate
  # side, and the counts recomputed so that the bundle is honest about itself.
  # Signed again afterwards, because a bundle whose numbers were edited is
  # refused at the signature long before anything reads the numbers.
  defp worse_by(dropped) do
    NetworkFixture.files()
    |> Map.update!("uplift-report.json", fn bytes ->
      bytes
      |> Jason.decode!()
      |> update_in(["payload", "task_deltas"], &lose_first(&1, dropped))
      |> recount()
      |> Jason.encode!()
    end)
    |> NetworkFixture.resign()
  end

  defp lose_first(deltas, dropped) do
    deltas
    |> Enum.with_index()
    |> Enum.map(fn {delta, index} ->
      if index < dropped, do: Map.put(delta, "candidate_reward", 0), else: delta
    end)
  end

  defp recount(envelope) do
    tally =
      Enum.frequencies_by(envelope["payload"]["task_deltas"], fn delta ->
        cond do
          delta["candidate_reward"] > delta["baseline_reward"] -> "wins"
          delta["candidate_reward"] < delta["baseline_reward"] -> "losses"
          true -> "ties"
        end
      end)

    update_in(envelope, ["payload", "primary_result"], fn result ->
      Enum.reduce(["wins", "losses", "ties"], result, fn outcome, acc ->
        Map.put(acc, outcome, Map.get(tally, outcome, 0))
      end)
    end)
  end
end
