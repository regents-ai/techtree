defmodule TechtreeWeb.RedirectController do
  @moduledoc """
  A retired address, sent on for good (301) to the page that took its place.
  The router names the new address in each route's assigns (`to`).
  """

  use TechtreeWeb, :controller

  def show(conn, _params) do
    conn
    |> put_status(:moved_permanently)
    |> redirect(to: conn.assigns.to)
  end
end
