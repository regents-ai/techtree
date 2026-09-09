defmodule TechtreeWeb.BlogController do
  use TechtreeWeb, :controller
  alias TechtreeWeb.Blog

  def index(conn, _params), do: render(conn, :index, page_title: "Blog", posts: Blog.all())

  def show(conn, %{"slug" => slug}) do
    case Blog.get(slug) do
      nil -> conn |> put_status(:not_found) |> render(:not_found, page_title: "Post not found")
      post -> render(conn, :show, page_title: post.title, post: post)
    end
  end
end
