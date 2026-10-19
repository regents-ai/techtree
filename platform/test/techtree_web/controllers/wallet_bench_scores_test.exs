defmodule TechtreeWeb.WalletBenchScoresTest do
  @moduledoc """
  `/wallet-bench.json`: the page's score grids as data for another site to show,
  each score linked to its result on techtree.sh, and nothing else.
  """

  use TechtreeWeb.ConnCase, async: false

  alias Techtree.WalletBenchFixture

  test "each test's grid, with every score linked to its result", %{conn: conn} do
    tests = WalletBenchFixture.seed!()

    Techtree.Repo.query!(
      "UPDATE wallet_bench_turns SET judgment = judgment || '{\"kept_only_here\": \"unlisted\"}' WHERE attempt_id = $1",
      [Ecto.UUID.dump!(tests.passed.id)]
    )

    conn = get(conn, ~p"/wallet-bench.json")
    assert get_resp_header(conn, "cache-control") == ["public, max-age=30"]
    body = json_response(conn, 200)

    refute Jason.encode!(body) =~ "unlisted"
    assert Map.keys(body) |> Enum.sort() == ~w(page read_at score tests)
    assert [%{"test" => "wallet"} = wallet, %{"test" => "install"} = install] = body["tests"]

    assert [
             %{"agent" => "Hermes Agent", "seconds" => 61, "overall" => 10.0, "cells" => cells}
             | _
           ] =
             wallet["rows"]

    assert [bankr, %{"wallet_tool" => "Foundry Cast", "state" => "not_tested"} | _] = cells

    assert bankr == %{
             "wallet_tool" => "Bankr",
             "state" => "scored",
             "score" => 10.0,
             "outcome" => "Pass",
             "result" => url(~p"/wallet-bench?#{[test: "wallet", result: tests.passed.id]}")
           }

    assert %{"state" => "cannot_run", "reason" => "It cannot run on a server."} =
             Enum.find(cells, &(&1["wallet_tool"] == "Coinbase Agentic Wallet"))

    assert length(wallet["wallet_tools"]) == length(cells)
    assert Enum.any?(install["rows"], &(&1["agent"] == "Cline"))
  end
end
