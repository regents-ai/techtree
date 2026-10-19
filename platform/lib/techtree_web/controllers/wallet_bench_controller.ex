defmodule TechtreeWeb.WalletBenchController do
  @moduledoc """
  The Wallet Bench for agents and other sites: `/wallet-bench.md`, the page's
  grids and list as Markdown (`TechtreeWeb.WalletBenchMD`), and
  `/wallet-bench.json`, the page's score grids as data, each score linked to
  its result on the page (`TechtreeWeb.WalletBenchScores`). Both are public and
  may be kept for 30 seconds.
  """

  use TechtreeWeb, :controller

  alias Techtree.WalletBench
  alias TechtreeWeb.{ExactResponse, Outage, WalletBenchScores}

  def markdown(conn, _params) do
    attempts = WalletBench.list_attempts!(load: [:turns, :model_spend_usd])
    generated_at = DateTime.utc_now() |> DateTime.truncate(:second)

    conn
    |> put_resp_header("cache-control", "public, max-age=30")
    |> put_resp_content_type("text/markdown", "utf-8")
    |> send_resp(200, TechtreeWeb.WalletBenchMD.render(attempts, generated_at))
  end

  @doc """
  The score grids as data (`TechtreeWeb.WalletBenchScores`). When the database
  can't be reached the answer is a 503 asking to try again; any other failure
  is the site's plain JSON 500.
  """
  def scores(conn, _params) do
    case Outage.read(&WalletBenchScores.read/0) do
      {:ok, scores} ->
        conn
        |> put_resp_header("cache-control", "public, max-age=30")
        |> json(scores)

      :database_down ->
        conn
        |> put_resp_header("retry-after", "30")
        |> ExactResponse.send_error(
          503,
          :scores_unavailable,
          "the Wallet Bench scores can't be read right now; try again shortly",
          "Wait the seconds in the Retry-After header, then ask again."
        )
    end
  end
end
