defmodule TechtreeWeb.WalletBenchController do
  @moduledoc """
  Public, read-only Wallet Bench exports: the index as Markdown and one
  attempt as explicitly projected JSON for Patchbay's results dialog.
  """

  use TechtreeWeb, :controller

  alias Techtree.WalletBench

  @detail_load [:machine, :turns, :payments, :model_spend_usd, :judge_cost_usd]

  def show(conn, %{"id" => id}) do
    with {:ok, id} <- Ecto.UUID.cast(id),
         {:ok, attempt} when not is_nil(attempt) <-
           WalletBench.get_attempt(id, load: @detail_load),
         {:ok, events} <- WalletBench.list_attempt_events(id) do
      conn
      |> put_resp_header("cache-control", "public, max-age=30")
      |> json(TechtreeWeb.WalletBenchJSON.show(attempt, events))
    else
      _missing ->
        conn
        |> put_status(:not_found)
        |> json(%{
          error: %{
            code: "not_found",
            message: "No recorded wallet run has that ID.",
            hint: "Choose a recorded run from /wallet-bench."
          }
        })
    end
  end

  def markdown(conn, _params) do
    attempts = WalletBench.list_attempts!(load: [:turns, :model_spend_usd])
    generated_at = DateTime.utc_now() |> DateTime.truncate(:second)

    conn
    |> put_resp_header("cache-control", "public, max-age=30")
    |> put_resp_content_type("text/markdown", "utf-8")
    |> send_resp(200, TechtreeWeb.WalletBenchMD.render(attempts, generated_at))
  end
end
