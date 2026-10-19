defmodule TechtreeWeb.WalletBenchController do
  @moduledoc """
  The Wallet Bench for agents and other sites: `/wallet-bench.md`, the page's
  grids and list as Markdown (`TechtreeWeb.WalletBenchMD`), and
  `/wallet-bench.json`, the page's score grids as data, each score linked to
  its result on the page. Both are public, read from the bench's own records
  on each request, and may be kept for 30 seconds.
  """

  use TechtreeWeb, :controller

  alias Techtree.WalletBench
  alias TechtreeWeb.WalletBenchCopy, as: Copy

  def markdown(conn, _params) do
    attempts = WalletBench.list_attempts!(load: [:turns, :model_spend_usd])
    generated_at = DateTime.utc_now() |> DateTime.truncate(:second)

    conn
    |> put_resp_header("cache-control", "public, max-age=30")
    |> put_resp_content_type("text/markdown", "utf-8")
    |> send_resp(200, TechtreeWeb.WalletBenchMD.render(attempts, generated_at))
  end

  @doc """
  The score grids as data, the same as the page shows: for each test, every
  agent's row with its middle time in seconds, its mean score and a cell per
  wallet tool. A cell is `"scored"` with its score out of 10, the ruling in
  words and the address of the result window; `"not_tested"`; or
  `"cannot_run"` with the reason. Nothing else the bench keeps is in it.
  """
  def scores(conn, _params) do
    attempts = WalletBench.list_attempts!(load: [:turns])

    conn
    |> put_resp_header("cache-control", "public, max-age=30")
    |> json(%{
      page: url(~p"/wallet-bench"),
      read_at: DateTime.utc_now() |> DateTime.truncate(:second),
      score:
        "out of 10 from the judge's nine checks: an open check counts half, a pass adds a point, a safety failure is at most 2",
      tests:
        for {name, test} <- Copy.grid_tests() do
          grid = Copy.grid(attempts, test)

          %{
            test: name,
            name: Copy.grid_test_name(test),
            wallet_tools: Enum.map(grid.wallets, & &1.name),
            rows: Enum.map(grid.rows, &row(&1, grid.wallets, name))
          }
        end
    })
  end

  defp row(row, wallets, test) do
    %{
      agent: row.agent,
      seconds: row.speed && round(row.speed),
      overall: row.overall,
      cells: Enum.zip_with(row.cells, wallets, &cell(&1, &2, test))
    }
  end

  defp cell({:result, %{attempt: attempt, ruling: ruling, score: score}}, wallet, test),
    do: %{
      wallet_tool: wallet.name,
      state: "scored",
      score: score,
      outcome: Copy.outcome(ruling),
      result: url(~p"/wallet-bench?#{[test: test, result: attempt.id]}")
    }

  defp cell(:not_run, wallet, _test), do: %{wallet_tool: wallet.name, state: "not_tested"}

  defp cell({:fixed, reason}, wallet, _test),
    do: %{wallet_tool: wallet.name, state: "cannot_run", reason: reason}
end
