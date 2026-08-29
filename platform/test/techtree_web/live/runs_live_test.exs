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
      {:ok, _live, html} = live(conn, ~p"/results")

      assert visible_text(html) =~ "Nobody has published a proof yet"
    end

    test "does not claim it opened with runs it has not got", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/results")

      refute visible_text(html) =~ "certification runs"
    end

    test "a run nobody published is not found", %{conn: conn} do
      assert_error_sent 404, fn ->
        live(conn, "/results/sha256:#{String.duplicate("a", 64)}")
      end
    end
  end

  describe "the log" do
    setup :publish_a_run

    test "shows when, the agent, the model, the counts, the difference and the grade",
         %{conn: conn, entry: entry} do
      {:ok, live, html} = live(conn, ~p"/results")
      text = visible_text(html)

      assert text =~ "hermes-agent 0.19.0"
      assert text =~ "qwen/qwen3.7-flash"

      assert has_element?(
               live,
               ~s|.runs-table__tasks span[title="#{entry.wins} better, #{entry.ties} same, #{entry.losses} worse"]|,
               "#{entry.wins} / #{entry.ties} / #{entry.losses}"
             )

      assert text =~ "+63.9%"
      assert text =~ "P1"
      assert text =~ Calendar.strftime(entry.accepted_at, "%d %b")
    end

    test "names the campaign and compares the baseline with the fallback Skill",
         %{conn: conn, entry: entry} do
      {:ok, live, _html} = live(conn, ~p"/results")

      assert has_element?(live, "#run-entry-#{entry.log_sequence}")
      assert visible_text(render(live)) =~ "Techtree Hello World"
      assert visible_text(render(live)) =~ "hello-world-v1 vs No Skill"
      refute has_element?(live, "#run-github-#{entry.log_sequence}")
    end

    test "keeps the publisher fingerprint off the scan-first proofs list",
         %{conn: conn, entry: entry} do
      {:ok, _live, html} = live(conn, ~p"/results")
      text = visible_text(html)

      assert text =~ "P1 participant-attested not independently reproduced"
      refute text =~ entry.participant_key_id
    end

    test "keeps the index focused on browsing and links to the proof boundary", %{conn: conn} do
      {:ok, live, html} = live(conn, ~p"/results")
      text = visible_text(html)

      assert text =~ "Proofs of controlled agent improvement."
      assert text =~ "Each proof binds a published task, a paired Skill result"
      assert text =~ "with task scoring"
      assert text =~ "Techtree checks the bundle’s integrity and internal consistency."
      assert text =~ "does not claim to have witnessed or independently reproduced the run."
      assert text =~ "This is a record, not a leaderboard."
      assert has_element?(live, ~s|a[href="/proofs"]|, "How verification works")
      assert has_element?(live, ".runs-index__lede .hoverdef__term", "verifiers")

      assert has_element?(
               live,
               ~s|.runs-index__lede .hoverdef__card a[href="https://github.com/PrimeIntellect-ai/verifiers"]|,
               "GitHub"
             )

      refute text =~ "the files match their recorded hashes"
      refute text =~ "It does not prove the Test happened as described."

      assert has_element?(
               live,
               ~s|.runs-index__intro[aria-labelledby="runs-index-title"] #runs-index-title|,
               "Published Skill Capsules"
             )

      assert has_element?(live, ".runs-table > li.runs-table__row")
    end

    test "rows carry no rank or position and nothing can reorder them", %{conn: conn} do
      {:ok, live, html} = live(conn, ~p"/results")

      rows =
        html |> LazyHTML.from_fragment() |> LazyHTML.query(".runs-table__row") |> LazyHTML.text()

      row_text = String.downcase(rows)

      for word <- ["rank", "leaderboard", "position", "sort by", "#1", "top "] do
        refute row_text =~ word, "a run row says #{inspect(word)}"
      end

      assert visible_text(html) =~ "This is a record, not a leaderboard."

      refute live |> element("select") |> has_element?()
      refute live |> element("[phx-click]") |> has_element?()
      refute html =~ "<form"
    end

    test "says once, of itself, that the log opened with this project's own runs",
         %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/results")
      text = visible_text(html)

      assert text =~ "own certification proofs"

      # It is one sentence the page makes about itself, so it is said once. A
      # second copy of it beside every row is the badge this ruling refused.
      assert length(String.split(text, "certification proofs")) == 2

      assert {run_at, _run_length} = :binary.match(text, "hello-world-v1 vs No Skill")

      assert {provenance_at, _provenance_length} =
               :binary.match(text, "own certification proofs")

      assert run_at < provenance_at
    end

    test "puts no label on a row saying whose run it is", %{conn: conn} do
      {:ok, _live, html} = live(conn, ~p"/results")

      rows =
        html |> LazyHTML.from_fragment() |> LazyHTML.query(".runs-table__row") |> LazyHTML.text()

      for word <- ["certification", "ours", "official", "verified by us", "techtree's"] do
        refute String.downcase(rows) =~ word, "a row is labelled #{inspect(word)}"
      end
    end

    test "does not offer the bytes it was submitted with", %{conn: conn, entry: entry} do
      {:ok, _live, html} = live(conn, ~p"/results")

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

      {:ok, _live, html} = live(conn, ~p"/results")

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

      {:ok, _live, html} = live(conn, ~p"/results")
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

      {:ok, _live, html} = live(conn, "/results?limit=1")

      assert shown(html) == [newest.bundle_digest]
      assert html =~ "before_sequence=#{newest.log_sequence}"

      {:ok, _live, older} = live(conn, "/results?limit=1&before_sequence=#{newest.log_sequence}")

      assert shown(older) == [Enum.at(entries, 1).bundle_digest]
    end
  end

  describe "one entry's own page" do
    setup :publish_a_run

    test "shows every task with both sides' rewards and the difference",
         %{conn: conn, entry: entry} do
      {:ok, _live, html} = live(conn, "/results/#{entry.bundle_digest}")
      text = visible_text(html)

      assert text =~ "36 tasks"

      for task <- entry.task_deltas do
        assert html =~ task["task_hash"]
      end

      first = hd(entry.task_deltas)

      assert text =~
               "Without the Skill #{first["baseline_reward"] * 100.0}% With the Skill " <>
                 "#{first["candidate_reward"] * 100.0}% Change +100.0%"
    end

    test "shows the coordinates the run pins, from the campaign this site publishes",
         %{conn: conn, entry: entry} do
      {:ok, _live, html} = live(conn, "/results/#{entry.bundle_digest}")
      text = visible_text(html)

      assert text =~ "36 tasks, fixed before either run"
      assert text =~ "44 model calls"
      assert text =~ entry.campaign_spec_digest
      assert text =~ entry.skill_digest
      assert text =~ entry.data_policy_digest
      assert text =~ entry.run_id
      assert text =~ "prime"
      assert html =~ ~s|href="/climbs/hello-world-climb"|
    end

    test "shows campaign and Skill metadata on the detail page", %{conn: conn, entry: entry} do
      {:ok, live, _html} = live(conn, "/results/#{entry.bundle_digest}")

      assert has_element?(live, "#run-comparison")
      assert visible_text(render(live)) =~ "Techtree Hello World"
      assert visible_text(render(live)) =~ "hello-world-v1 vs No Skill"
      refute has_element?(live, "#run-subtitle")

      assert has_element?(
               live,
               "#run-outcome",
               "+63.9% score difference · #{entry.wins} better, #{entry.ties} same, #{entry.losses} worse."
             )

      refute has_element?(live, "#run-github")
    end

    test "calls its place in the log a log sequence and never a position",
         %{conn: conn, entry: entry} do
      {:ok, _live, html} = live(conn, "/results/#{entry.bundle_digest}")
      text = visible_text(html)

      assert text =~ "Log sequence #{entry.log_sequence}"

      for word <- ["rank", "position", "place #", "top "] do
        refute String.downcase(text) =~ word, "the page says #{inspect(word)}"
      end
    end

    test "summarizes passed verification and links to its exact meaning",
         %{conn: conn, entry: entry} do
      {:ok, _live, html} = live(conn, "/results/#{entry.bundle_digest}")
      text = visible_text(html)

      count = Techtree.Network.Bundle.check_count()

      assert text =~ "#{count} checks passed"
      assert text =~ "Bundle verification passed."
      assert text =~ "How verification works."
      refute text =~ "the submission is small enough to be a proof bundle"
    end

    test "filters task evidence by outcome", %{conn: conn, entry: entry} do
      {:ok, live, _html} = live(conn, "/results/#{entry.bundle_digest}")

      assert has_element?(live, ~s|button[phx-value-filter="better"]|, "Better #{entry.wins}")
      assert task_row_count(render(live)) == entry.wins + entry.ties + entry.losses

      live |> element(~s|button[phx-value-filter="better"]|) |> render_click()

      assert has_element?(live, ~s|button[phx-value-filter="better"][aria-pressed="true"]|)
      assert task_row_count(render(live)) == entry.wins
    end

    test "offers the verified projection and never the submitted bytes",
         %{conn: conn, entry: entry} do
      {:ok, _live, html} = live(conn, "/results/#{entry.bundle_digest}")

      assert html =~ ~s|href="/api/v1/publications/#{entry.bundle_digest}"|
      refute html =~ "/api/v1/submissions"
      refute html =~ entry.submission_bytes
    end

    test "makes the offline verification command specific to this run",
         %{conn: conn, entry: entry} do
      {:ok, live, _html} = live(conn, "/results/#{entry.bundle_digest}")

      assert has_element?(
               live,
               ~s|#copy-runs-verify[data-copy-value="techtree proof verify #{entry.run_id}"]|
             )
    end

    test "a withdrawn entry keeps its page and is marked at the top of it",
         %{conn: conn, entry: entry, keys: keys} do
      {:ok, marked, :recorded} =
        Ingest.withdraw(NetworkFixture.withdrawal(entry.bundle_digest, keys))

      {:ok, _live, html} = live(conn, "/results/#{entry.bundle_digest}")
      text = visible_text(html)

      assert text =~ "Withdrawn by the participant"
      assert text =~ Calendar.strftime(marked.withdrawn_at, "%-d %B %Y")

      # It is marked, not emptied: everything it published is still there.
      assert text =~ "qwen/qwen3.7-flash"
      assert text =~ entry.run_id
      assert html =~ hd(entry.task_deltas)["task_hash"]
    end
  end

  describe "stored Skill metadata" do
    setup :publish_a_run_with_metadata

    test "shows the stored Skill name and canonical GitHub link on both pages",
         %{conn: conn, entry: entry} do
      github_url = "https://github.com/example/hello-world"

      {:ok, index, _html} = live(conn, ~p"/results")

      assert has_element?(index, "#run-entry-#{entry.log_sequence}")
      assert visible_text(render(index)) =~ "branchcode vs No Skill"

      assert has_element?(
               index,
               "#run-entry-#{entry.log_sequence} #run-github-#{entry.log_sequence}[href=\"#{github_url}\"]"
             )

      {:ok, detail, _html} = live(conn, "/results/#{entry.bundle_digest}")

      assert has_element?(detail, "#run-comparison")
      assert visible_text(render(detail)) =~ "branchcode vs No Skill"
      assert has_element?(detail, "#run-github[href=\"#{github_url}\"]")
    end
  end

  defp shown(html) do
    ~r|/results/(sha256:[0-9a-f]{64})|
    |> Regex.scan(html, capture: :all_but_first)
    |> List.flatten()
    |> Enum.uniq()
  end

  defp task_row_count(html), do: length(Regex.scan(~r/<li class="tasks__row">/, html))

  defp publish_a_run(_context) do
    keys = NetworkFixture.key_pair()
    files = NetworkFixture.resign(NetworkFixture.files(), keys: keys)

    {:ok, entry, :recorded} = NetworkFixture.publish(NetworkFixture.submission(files))

    {:ok, entry: entry, keys: keys}
  end

  defp publish_a_run_with_metadata(_context) do
    keys = NetworkFixture.key_pair()
    files = NetworkFixture.resign(NetworkFixture.files(), keys: keys)

    {:ok, entry, :recorded} =
      NetworkFixture.publish(
        NetworkFixture.submission(files),
        skill_name: "branchcode",
        skill_github_url: "https://github.com/example/hello-world"
      )

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
