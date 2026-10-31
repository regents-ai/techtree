defmodule TechtreeWeb.ShareCardController do
  @moduledoc """
  The share pictures (`TechtreeWeb.ShareCard`), drawn from stored records for
  whoever asks, a site making a link preview included: a published Result's,
  which a withdrawn Result keeps as it keeps its page, and the Wallet Bench's,
  from the scores the bench publishes (`TechtreeWeb.WalletBenchScores`).
  """

  use TechtreeWeb, :controller

  alias Techtree.Network.Query
  alias TechtreeWeb.{Outage, ShareCard, WalletBenchScores}

  # The body is a PNG drawn by the site, sent as image/png.
  # sobelow_skip ["XSS.ContentType", "XSS.SendResp"]
  def result(conn, %{"bundle_digest" => digest}) do
    case Query.get_entry(digest) do
      {:ok, entry} ->
        conn
        |> put_resp_header("cache-control", "public, max-age=86400")
        |> put_resp_content_type("image/png", nil)
        |> send_resp(200, ShareCard.result_png(entry))

      :error ->
        raise TechtreeWeb.NotFoundError, "no run is published under that fingerprint"
    end
  end

  @doc """
  The Wallet Bench's picture, of the grid as the scores stand now: the page
  names it with a version of them, so a new grid is a new address. Drawn once
  for each version and kept with the scores (`WalletBenchScores.picture/0`),
  and kept by readers for five minutes. When the scores can't be read the
  answer is 503, asked again in a minute.
  """
  # The body is a PNG drawn by the site, sent as image/png.
  # sobelow_skip ["XSS.ContentType", "XSS.SendResp"]
  def wallet_bench(conn, _params) do
    case Outage.read(&WalletBenchScores.picture/0) do
      {:ok, png} ->
        conn
        |> put_resp_header("cache-control", "public, max-age=300")
        |> put_resp_content_type("image/png", nil)
        |> send_resp(200, png)

      :database_down ->
        conn |> put_resp_header("retry-after", "60") |> send_resp(503, "")
    end
  end
end
