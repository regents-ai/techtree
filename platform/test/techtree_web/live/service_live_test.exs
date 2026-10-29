defmodule TechtreeWeb.ServiceLiveTest do
  @moduledoc """
  The two offer pages count their Agent Wallet Bench figures from the scores
  `/wallet-bench.json` serves, on the page and in its Markdown, so neither can
  say a different number from the bench.
  """

  use TechtreeWeb.ConnCase, async: false

  import Phoenix.LiveViewTest

  alias Techtree.WalletBenchFixture
  alias TechtreeWeb.WalletBenchScores

  setup do
    WalletBenchScores.delete_all()
    on_exit(fn -> WalletBenchScores.delete_all() end)

    tests = WalletBenchFixture.seed!()
    # The wallet pass left a key in a plain file, and Claude Code's install,
    # on a later day, was a safety failure.
    WalletBenchFixture.flag_wallet_pass!(tests.passed)
    safety_failure!(~U[2026-11-02 09:00:00.000000Z])
    WalletBenchScores.delete_all()
    :ok
  end

  defp safety_failure!(at) do
    machine = Techtree.WalletBench.Machine |> Ash.read!(authorize?: false) |> hd()

    attempt =
      Ash.Seed.seed!(Techtree.WalletBench.Attempt, %{
        batch_id: machine.batch_id,
        replicate: 1,
        harness_id: "H05",
        wallet_id: "W03",
        state: :done,
        plan: :wallet,
        machine_id: machine.id,
        inserted_at: at
      })

    Ash.Seed.seed!(Techtree.WalletBench.Turn, %{
      attempt_id: attempt.id,
      test: :T1a,
      state: :judged,
      prompt: "Install the wallet tool.",
      wall_seconds: Decimal.new(30),
      inserted_at: at,
      judgment: %{
        "outcome" => "FAILED_SAFETY",
        "criteria" => Map.new(1..9, &{"C#{&1}", %{"value" => "true", "reason" => "r"}})
      }
    })
  end

  # The figures counted again here from the feed itself: its scored boxes,
  # their agents, the wallet passes and the flagged ones among them.
  defp from_feed(conn) do
    tests = conn |> get(~p"/wallet-bench.json") |> json_response(200) |> Map.fetch!("tests")

    scored =
      for test <- tests,
          row <- test["rows"],
          %{"state" => "scored"} = cell <- row["cells"],
          do: {test["test"], row["agent"], cell["outcome"]}

    working =
      for {"wallet", _agent, outcome} <- scored,
          outcome == "Pass" or String.starts_with?(outcome, "Pass, flagged"),
          do: outcome

    %{
      agents: scored |> Enum.map(&elem(&1, 1)) |> Enum.uniq() |> length(),
      working: length(working),
      plain_file: Enum.count(working, &String.starts_with?(&1, "Pass, flagged")),
      judged: length(scored),
      safety: Enum.count(scored, &(elem(&1, 2) == "Safety failure"))
    }
  end

  test "each offer page shows the figures the scores feed counts", %{conn: conn} do
    feed = from_feed(conn)
    assert feed == %{agents: 2, working: 1, plain_file: 1, judged: 4, safety: 1}

    for path <- [~p"/services/verify", ~p"/services/cyber-assist"] do
      {:ok, live, _html} = live(conn, path)

      assert figures(live) == [
               {"#{feed.agents}", "coding agents tested"},
               {"#{feed.plain_file} of #{feed.working}",
                "working wallet they set up left their key or unlock password in a plain file"},
               {"#{feed.safety}", "safety failure in #{feed.judged} judged tests"}
             ]

      assert has_element?(
               live,
               ".service-result .eyebrow",
               "Our own bench, tests run 14 October to 2 November 2026"
             )
    end
  end

  test "each offer's Markdown says the same figures in words", %{conn: conn} do
    feed = from_feed(conn)

    for path <- [~p"/services/verify", ~p"/services/cyber-assist"] do
      text = conn |> put_req_header("accept", "text/markdown") |> get(path) |> response(200)

      assert text =~
               "Our own bench, tests run 14 October to 2 November 2026: " <>
                 "#{feed.agents} coding agents tested; " <>
                 "#{feed.plain_file} of #{feed.working} working wallet they set up left their key or unlock password in a plain file. " <>
                 "#{feed.safety} safety failure in #{feed.judged} judged tests. [See the bench](/wallet-bench)."

      refute text =~ "{{"
    end
  end

  test "each offer's page and Markdown start the same email", %{conn: conn} do
    for {offer, path} <- [verify: ~p"/services/verify", cyber_assist: ~p"/services/cyber-assist"] do
      mailto = TechtreeWeb.ServiceLive.mailto(offer)
      {:ok, live, _html} = live(conn, path)
      text = conn |> put_req_header("accept", "text/markdown") |> get(path) |> response(200)

      assert has_element?(live, ~s|.service-offer__start a[href="#{mailto}"]|)
      assert text =~ "(#{mailto})"
      assert %URI{path: "build@regents.sh", query: query} = URI.parse(mailto)
      assert %{"subject" => _subject, "body" => body} = URI.decode_query(query)
      assert ["Company:", "Product:" | _rest] = String.split(body, "\r\n")
    end
  end

  test "with nothing judged yet the pages say so, not a range of days", %{conn: conn} do
    Techtree.Repo.query!("UPDATE wallet_bench_turns SET judgment = NULL")
    WalletBenchScores.delete_all()

    {:ok, live, _html} = live(conn, ~p"/services/verify")
    assert has_element?(live, ".service-result .eyebrow", "Our own bench, no tests judged yet")
    assert [{"0", "coding agents tested"} | _figures] = figures(live)
  end

  defp figures(live) do
    live
    |> element(".service-result__figures")
    |> render()
    |> LazyHTML.from_fragment()
    |> LazyHTML.query(".service-result__figures > div")
    |> Enum.map(fn div ->
      {div |> LazyHTML.query("dd") |> LazyHTML.text() |> String.trim(),
       div |> LazyHTML.query("dt") |> LazyHTML.text() |> String.trim()}
    end)
  end
end
