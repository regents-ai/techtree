defmodule TechtreeWeb.PublicPagesController do
  @moduledoc """
  About, Contact and Privacy as pages, and the agent guide at `/llms.txt`, all
  from `TechtreeWeb.PublicDocuments`. Their Markdown is answered before the
  router.
  """

  use TechtreeWeb, :controller

  alias TechtreeWeb.PublicDocuments

  def show(conn, _params) do
    page = PublicDocuments.page(conn.request_path)
    render(conn, :show, page: page, page_title: page.title)
  end

  def llms(conn, _params) do
    conn
    |> put_resp_content_type("text/plain")
    |> put_resp_header("cache-control", "public")
    |> send_resp(200, PublicDocuments.llms())
  end
end
