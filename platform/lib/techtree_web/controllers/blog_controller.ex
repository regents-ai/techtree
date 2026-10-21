defmodule TechtreeWeb.BlogController do
  use TechtreeWeb, :controller
  alias TechtreeWeb.Blog

  # The blog has no page until it has a post.
  def index(conn, _params) do
    case Blog.all() do
      [] -> conn |> put_status(:not_found) |> render(:not_found, page_title: "Blog")
      posts -> render(conn, :index, page_title: "Blog", posts: posts)
    end
  end

  def show(conn, %{"slug" => slug}) do
    case Blog.get(slug) do
      nil -> conn |> put_status(:not_found) |> render(:not_found, page_title: "Post not found")
      post -> render(conn, :show, page_title: post.title, post: post)
    end
  end
end
