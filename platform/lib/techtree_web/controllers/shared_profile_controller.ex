defmodule TechtreeWeb.SharedProfileController do
  use TechtreeWeb, :controller

  def read(conn, _params), do: RegentIdentity.HTTP.call(%{conn | path_info: []}, :techtree)
  def update(conn, _params), do: RegentIdentity.HTTP.call(%{conn | path_info: []}, :techtree)
  def sync(conn, _params), do: RegentIdentity.HTTP.call(%{conn | path_info: ["sync"]}, :techtree)

  def show(conn, _params) do
    conn
    |> put_resp_header("cache-control", "no-store")
    |> render(:show, page_title: "Profile", shared_profile_page: true)
  end
end
