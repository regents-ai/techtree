defmodule TechtreeWeb.WalletBenchScoresTest do
  @moduledoc """
  `/wallet-bench.json`: the page's score grids as data for another site to show,
  each score linked to its result on techtree.sh, worked out by Postgres and
  kept for 30 seconds, and nothing else.
  """

  use TechtreeWeb.ConnCase, async: false

  alias Techtree.WalletBench
  alias Techtree.WalletBenchFixture
  alias TechtreeWeb.WalletBenchCopy, as: Copy
  alias TechtreeWeb.WalletBenchScores

  setup do
    WalletBenchScores.delete_all()
    on_exit(fn -> WalletBenchScores.delete_all() end)
    %{tests: WalletBenchFixture.seed!()}
  end

  defp keys(map), do: map |> Map.keys() |> Enum.sort()

  test "each test's grid, every field named, every score linked to its result", %{
    conn: conn,
    tests: tests
  } do
    Techtree.Repo.query!(
      "UPDATE wallet_bench_turns SET judgment = judgment || '{\"kept_only_here\": \"unlisted\"}' WHERE attempt_id = $1",
      [Ecto.UUID.dump!(tests.passed.id)]
    )

    conn = get(conn, ~p"/wallet-bench.json")
    assert get_resp_header(conn, "cache-control") == ["public, max-age=30"]
    body = json_response(conn, 200)

    refute Jason.encode!(body) =~ "unlisted"
    assert keys(body) == ~w(page read_at score tests)
    assert [%{"test" => "wallet"} = wallet, %{"test" => "install"} = install] = body["tests"]
    assert keys(wallet) == ~w(name rows test wallet_tools)

    assert [%{"agent" => "Hermes Agent"} = hermes | _] = wallet["rows"]
    assert keys(hermes) == ~w(agent cells overall seconds)
    assert %{"seconds" => 61, "overall" => 10.0} = hermes

    [bankr, foundry | _] = hermes["cells"]
    assert keys(bankr) == ~w(outcome result score state wallet_tool)

    assert bankr == %{
             "wallet_tool" => "Bankr",
             "state" => "scored",
             "score" => 10.0,
             "outcome" => "Pass",
             "result" => url(~p"/wallet-bench?#{[test: "wallet", result: tests.passed.id]}")
           }

    assert foundry == %{"wallet_tool" => "Foundry Cast", "state" => "not_tested"}

    assert %{"state" => "cannot_run", "reason" => "It cannot run on a server."} =
             cannot =
             Enum.find(hermes["cells"], &(&1["wallet_tool"] == "Coinbase Agentic Wallet"))

    assert keys(cannot) == ~w(reason state wallet_tool)
    assert length(wallet["wallet_tools"]) == length(hermes["cells"])
    assert Enum.any?(install["rows"], &(&1["agent"] == "Cline"))
  end

  # The page and the feed build their grids from the same pieces; Postgres's
  # answer must be the page's own.
  test "the feed's grids are the page's grids" do
    # An install that was retried after a safety failure: the failure stands.
    machine = Techtree.WalletBench.Machine |> Ash.read!(authorize?: false) |> hd()

    attempt =
      Ash.Seed.seed!(Techtree.WalletBench.Attempt, %{
        batch_id: machine.batch_id,
        replicate: 1,
        harness_id: "H05",
        wallet_id: "W03",
        state: :done,
        plan: :wallet,
        machine_id: machine.id
      })

    for {test, outcome, at} <- [{:T1a, "FAILED_SAFETY", 0}, {:T1b, "PASS", 60}] do
      Ash.Seed.seed!(Techtree.WalletBench.Turn, %{
        attempt_id: attempt.id,
        test: test,
        state: :judged,
        prompt: "Install the wallet tool.",
        wall_seconds: Decimal.new(30 + at),
        inserted_at: DateTime.add(DateTime.utc_now(), at),
        judgment: %{
          "outcome" => outcome,
          "criteria" => Map.new(1..9, &{"C#{&1}", %{"value" => "true", "reason" => "r"}})
        }
      })
    end

    # An older test of the same pair that passed: the newer one is the pair's.
    older =
      Ash.Seed.seed!(Techtree.WalletBench.Attempt, %{
        batch_id: machine.batch_id,
        replicate: 2,
        harness_id: "H05",
        wallet_id: "W03",
        state: :done,
        plan: :wallet,
        machine_id: machine.id,
        inserted_at: ~U[2026-10-01 00:00:00.000000Z]
      })

    Ash.Seed.seed!(Techtree.WalletBench.Turn, %{
      attempt_id: older.id,
      test: :T1a,
      state: :judged,
      prompt: "Install the wallet tool.",
      judgment: %{
        "outcome" => "PASS",
        "criteria" => Map.new(1..9, &{"C#{&1}", %{"value" => "true", "reason" => "r"}})
      }
    })

    attempts = WalletBench.list_attempts!(load: [:turns])

    assert {:result, %{score: 2.0}} =
             Copy.grid(attempts, :install).rows
             |> Enum.find(&(&1.agent == "Claude Code"))
             |> Map.fetch!(:cells)
             |> Enum.at(2)

    %{tests: feed} = WalletBenchScores.read()

    for {name, test} <- Copy.grid_tests() do
      page = Copy.grid(attempts, test)
      %{rows: rows} = Enum.find(feed, &(&1.test == name))

      assert Enum.map(rows, & &1.agent) == Enum.map(page.rows, & &1.agent)

      for {row, page_row} <- Enum.zip(rows, page.rows) do
        assert row.overall == page_row.overall
        assert row.seconds == (page_row.speed && round(page_row.speed))
        assert Enum.map(row.cells, &(&1[:score] || &1.state)) == Enum.map(page_row.cells, &cell/1)
      end
    end
  end

  defp cell({:result, %{score: score}}), do: score
  defp cell(:not_run), do: "not_tested"
  defp cell({:fixed, _reason}), do: "cannot_run"

  test "three readers in a row make one set of database reads", %{conn: conn} do
    handler = "scores-reads-#{System.unique_integer()}"
    parent = self()

    :telemetry.attach(
      handler,
      [:techtree, :repo, :query],
      fn _event, _measurements, %{query: query}, _config ->
        if query =~ "wallet_bench_turns", do: send(parent, :read)
      end,
      nil
    )

    on_exit(fn -> :telemetry.detach(handler) end)

    for _reader <- 1..3, do: assert(conn |> get(~p"/wallet-bench.json") |> json_response(200))

    reads = Stream.repeatedly(fn -> receive do: (:read -> 1), after: (0 -> nil) end)
    # Two tests, each with its newest rulings and its middle times.
    assert reads |> Enum.take_while(& &1) |> Enum.sum() == 4
  end

  test "any other failure is the plain JSON error, with nothing from inside", %{
    conn: conn,
    tests: tests
  } do
    Techtree.Repo.query!(
      "UPDATE wallet_bench_turns SET judgment = judgment - 'criteria' WHERE attempt_id = $1",
      [Ecto.UUID.dump!(tests.passed.id)]
    )

    {status, _headers, body} = assert_error_sent 500, fn -> get(conn, ~p"/wallet-bench.json") end

    assert status == 500
    assert %{"error" => %{"code" => "internal_server_error"} = error} = Jason.decode!(body)
    assert Map.keys(error) |> Enum.sort() == ~w(code hint message)
    refute body =~ "Error)" or body =~ "criteria" or body =~ "wallet_bench"
  end
end
