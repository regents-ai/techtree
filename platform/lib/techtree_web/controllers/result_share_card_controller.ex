defmodule TechtreeWeb.ResultShareCardController do
  @moduledoc """
  A published Result's share picture (`TechtreeWeb.ResultShareCard`), drawn
  from its stored record for whoever asks, a site making a link preview
  included. A withdrawn Result keeps its picture, as it keeps its page.
  """

  use TechtreeWeb, :controller

  alias Techtree.Network.Query
  alias TechtreeWeb.ResultShareCard

  # The body is a PNG drawn by the site, sent as image/png.
  # sobelow_skip ["XSS.ContentType", "XSS.SendResp"]
  def show(conn, %{"bundle_digest" => digest}) do
    case Query.get_entry(digest) do
      {:ok, entry} ->
        conn
        |> put_resp_header("cache-control", "public, max-age=86400")
        |> put_resp_content_type("image/png", nil)
        |> send_resp(200, ResultShareCard.png(entry))

      :error ->
        raise TechtreeWeb.NotFoundError, "no run is published under that fingerprint"
    end
  end
end
