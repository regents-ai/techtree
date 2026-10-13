defmodule TechtreeWeb.WalletBenchController do
  @moduledoc """
  The Wallet Bench for agents: `/wallet-bench.md`, the page's answer and list
  as Markdown (`TechtreeWeb.WalletBenchMD`). Public, and may be kept for 30
  seconds.
  """

  use TechtreeWeb, :controller

  alias Techtree.WalletBench

  def markdown(conn, _params) do
    attempts = WalletBench.list_attempts!(load: [:turns, :model_spend_usd])
    generated_at = DateTime.utc_now() |> DateTime.truncate(:second)

    conn
    |> put_resp_header("cache-control", "public, max-age=30")
    |> put_resp_content_type("text/markdown", "utf-8")
    |> send_resp(200, TechtreeWeb.WalletBenchMD.render(attempts, generated_at))
  end
end
