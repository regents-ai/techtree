defmodule TechtreeWeb.PagesController do
  @moduledoc """
  About, Contact and Privacy: who runs Techtree, how to reach them, and what is
  kept about a visitor. Each answers as a page or as Markdown.
  """

  use TechtreeWeb, :controller

  alias TechtreeWeb.MD

  def about(conn, _params), do: answer(conn, :about)
  def contact(conn, _params), do: answer(conn, :contact)
  def privacy(conn, _params), do: answer(conn, :privacy)

  defp answer(conn, name) do
    case get_format(conn) do
      "md" ->
        MD.answer(conn, name)

      "html" ->
        page = MD.page(name)
        render(conn, :show, page: page, page_title: page.title)
    end
  end
end
