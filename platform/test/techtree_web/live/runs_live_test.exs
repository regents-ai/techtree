defmodule TechtreeWeb.RunsLiveTest do
  @moduledoc """
  What the two pages of the run log show, and what they refuse to show.

  Several of these tests are about absences, and the absences are the point. A
  log that grew a position number, a sort control, or a sentence somebody typed
  would still render; it would just no longer be the thing that was designed.

  So the order is asserted against a deliberately unhelpful set of entries: three
  runs published one after another, each with a worse result than the one before
  it. A page that ordered by result would show them in exactly the opposite
  order to a page that logs, which is what makes the assertion mean something.

  A withdrawn entry is checked for being *present* rather than absent, which is
  the founder's ruling: the entry stays visible, marked withdrawn, because a
  log that dropped its withdrawn entries would have gaps nothing explained.
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
      {:ok, _live, html} = live(conn, ~p"/runs")

      assert visible_text(html) =~ "Nobody has published a run yet"
    end

    test "a run nobody published is not found", %{conn: conn} do
      assert_error_sent 404, fn ->
        live(conn, "/runs/sha256:#{String.duplicate("a", 64)}")
      end
    end
  end

  describe "the log" do
    setup :publish_a_run

    test "shows when, the agent, the model, the counts, the difference and the grade",
         %{conn: conn, entry: entry} do
      {:ok, _live, html} = live(conn, ~p"/runs")
      text = visible_text(html)

      assert text =~ "hermes-agent 0.19.0"
      assert text =~ "qwen/qwen3.7-flash"
      assert text =~ "#{entry.wins} better"
      assert text =~ "#{entry.ties} same"
      assert text =~ "#{entry.losses} worse"
      assert text =~ "+0.639"
      assert text =~ "P1"
      assert text =~ Calendar.strftime(entry.accepted_at, "%Y-%m-%d")
    end

    test "names the publisher by a short form of their key's fingerprint",
         %{conn: conn, entry: entry} do
      {:ok, _live, html} = live(conn, ~p"/runs")
      text = visible_text(html)

      "sha256:" <> hex = entry.participant_key_id

      assert text =~ "sha256:" <> String.slice(hex, 0, 12)
      refute text =~ entry.participant_key_id
    end

    test "says what this site checked and what it did not", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/runs")
      text = visible_text(html)

      assert text =~ "internally consistent and signed by the key it names"
      assert text =~ "not a claim that the run happened"
      assert text =~ "did not watch it and has not repeated it"
    end

    test "carries no rank, no position and nothing to reorder it by", %{conn: conn} do
      {:ok, live, html} = live(conn, ~p"/runs")
      text = html |> visible_text() |> String.downcase()

      for word <- ["rank", "leaderboard", "position", "sort by", "#1", "top "] do
        refute text =~ word, "the log says #{inspect(word)}"
      end

      refute live |> element("select") |> has_element?()
      refute live |> element("[phx-click]") |> has_element?()
      refute html =~ "<form"
    end

    test "does not offer the bytes it was submitted with", %{conn: conn, entry: entry} do
      {:ok, _live, html} = live(conn, ~p"/runs")

      refute html =~ "/api/v1/submissions"
      refute html =~ Base.encode64(NetworkFixture.files()["data-policy.json"])
      refute html =~ entry.submission_bytes
    end
  end

  describe "the log with several entries" do
    setup :publish_several_runs

    test "is in arrival order, newest first, and not in order of result",
         %{conn: conn, entries: entries} do
      arrived = Enum.map(entries, & &1.bundle_digest)

      # The setup is only worth anything if the results really do run downhill.
      assert Enum.map(entries, & &1.wins) == [23, 14, 7]

      {:ok, _live, html} = live(conn, ~p"/runs")

      assert shown(html) == Enum.reverse(arrived)

      by_result = entries |> Enum.sort_by(& &1.wins, :desc) |> Enum.map(& &1.bundle_digest)

      refute shown(html) == by_result
    end

    test "a withdrawn entry keeps its place and says who took it off",
         %{conn: conn, entries: entries, keys: keys} do
      withdrawn = Enum.at(entries, 1)

      {:ok, marked, :recorded} =
        Ingest.withdraw(
          NetworkFixture.withdrawal(withdrawn.bundle_digest, keys[withdrawn.bundle_digest])
        )

      {:ok, _live, html} = live(conn, ~p"/runs")
      text = visible_text(html)

      assert html =~ withdrawn.bundle_digest
      assert text =~ "Withdrawn by the participant on"
      assert text =~ Calendar.strftime(marked.withdrawn_at, "%-d %B %Y")

      for kept <- entries do
        assert html =~ kept.bundle_digest
      end
    end

    test "reads one keyset page at a time, oldest link forward", %{conn: conn, entries: entries} do
      newest = List.last(entries)

      {:ok, _live, html} = live(conn, "/runs?limit=1")

      assert shown(html) == [newest.bundle_digest]
      assert html =~ "before_sequence=#{newest.log_sequence}"

      {:ok, _live, older} = live(conn, "/runs?limit=1&before_sequence=#{newest.log_sequence}")

      assert shown(older) == [Enum.at(entries, 1).bundle_digest]
    end
  end

  describe "one entry's own page" do
    setup :publish_a_run

    test "shows every task with both sides' rewards and the difference",
         %{conn: conn, entry: entry} do
      {:ok, _live, html} = live(conn, "/runs/#{entry.bundle_digest}")
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
      {:ok, _live, html} = live(conn, "/runs/#{entry.bundle_digest}")
      text = visible_text(html)

      assert text =~ "36 tasks, fixed before either run"
      assert text =~ "44 model calls"
      assert text =~ entry.campaign_spec_digest
      assert text =~ entry.data_policy_digest
      assert text =~ entry.run_id
      assert text =~ "prime"
      assert html =~ ~s|href="/campaigns/hello-world-climb"|
    end

    test "calls its place in the log a log sequence and never a position",
         %{conn: conn, entry: entry} do
      {:ok, _live, html} = live(conn, "/runs/#{entry.bundle_digest}")
      text = visible_text(html)

      assert text =~ "Log sequence #{entry.log_sequence}"

      for word <- ["rank", "position", "place #", "top "] do
        refute String.downcase(text) =~ word, "the page says #{inspect(word)}"
      end
    end

    test "lists the checks that ran, how many passed, and what none of them prove",
         %{conn: conn, entry: entry} do
      {:ok, _live, html} = live(conn, "/runs/#{entry.bundle_digest}")
      text = visible_text(html)

      count = Techtree.Network.Bundle.check_count()

      assert text =~ "#{count} of #{count} passed"

      for {_name, sentence} <- Techtree.Network.Bundle.checks() do
        assert text =~ sentence
      end

      assert text =~ "None of them is a claim that the run happened"
      assert text =~ "did not watch it and has not repeated it"
    end

    test "offers the verified projection and never the submitted bytes",
         %{conn: conn, entry: entry} do
      {:ok, _live, html} = live(conn, "/runs/#{entry.bundle_digest}")

      assert html =~ ~s|href="/api/v1/publications/#{entry.bundle_digest}"|
      refute html =~ "/api/v1/submissions"
      refute html =~ entry.submission_bytes
    end

    test "a withdrawn entry keeps its page and is marked at the top of it",
         %{conn: conn, entry: entry, keys: keys} do
      {:ok, marked, :recorded} =
        Ingest.withdraw(NetworkFixture.withdrawal(entry.bundle_digest, keys))

      {:ok, _live, html} = live(conn, "/runs/#{entry.bundle_digest}")
      text = visible_text(html)

      assert text =~ "Withdrawn by the participant"
      assert text =~ Calendar.strftime(marked.withdrawn_at, "%-d %B %Y")

      # It is marked, not emptied: everything it published is still there.
      assert text =~ "qwen/qwen3.7-flash"
      assert text =~ entry.run_id
      assert html =~ hd(entry.task_deltas)["task_hash"]
    end
  end

  defp shown(html) do
    ~r|/runs/(sha256:[0-9a-f]{64})|
    |> Regex.scan(html, capture: :all_but_first)
    |> List.flatten()
    |> Enum.uniq()
  end

  defp publish_a_run(_context) do
    keys = NetworkFixture.key_pair()
    files = NetworkFixture.resign(NetworkFixture.files(), keys: keys)

    {:ok, entry, :recorded} = NetworkFixture.publish(NetworkFixture.submission(files))

    {:ok, entry: entry, keys: keys}
  end

  # Three entries whose results run downhill as they arrive, so that a page
  # ordered by result would show them in exactly the opposite order. Each is
  # signed by its own key, and the keys are kept so that a withdrawal can be
  # signed by the one that published.
  defp publish_several_runs(_context) do
    published =
      for dropped <- [0, 10, 20] do
        keys = NetworkFixture.key_pair()
        files = NetworkFixture.resign(worse_by_files(dropped), keys: keys)

        {:ok, entry, :recorded} = NetworkFixture.publish(NetworkFixture.submission(files))

        {entry, keys}
      end

    {:ok,
     entries: Enum.map(published, &elem(&1, 0)),
     keys: Map.new(published, &{elem(&1, 0).bundle_digest, elem(&1, 1)})}
  end

  # The same run with the first `dropped` tasks scoring nothing on the candidate
  # side, and the counts recomputed so that the bundle is honest about itself.
  defp worse_by_files(dropped) do
    Map.update!(NetworkFixture.files(), "uplift-report.json", fn bytes ->
      bytes
      |> Jason.decode!()
      |> update_in(["payload", "task_deltas"], &lose_first(&1, dropped))
      |> recount()
      |> Jason.encode!()
    end)
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
