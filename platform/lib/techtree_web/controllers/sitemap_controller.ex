defmodule TechtreeWeb.SitemapController do
  @moduledoc """
  Every public page a search engine should index: the fixed pages, each blog
  post, each Climb in the active release, and each published Result that has
  not been withdrawn.
  """

  use TechtreeWeb, :controller

  alias Techtree.Catalog
  alias Techtree.Network
  alias Techtree.Network.Projection
  alias TechtreeWeb.Blog

  @fixed ~w(/ /start /results /verify /docs /changelog /repo2rlenv /blog /about /contact /privacy /terms)

  def index(conn, _params) do
    conn
    |> put_resp_content_type("application/xml")
    |> send_resp(200, document(urls()))
  end

  defp urls do
    origin = TechtreeWeb.Endpoint.url()

    Enum.map(@fixed, &(origin <> &1)) ++
      Enum.map(Blog.all(), &(origin <> "/blog/" <> &1.slug)) ++
      Enum.map(Catalog.Query.list_climbs(), &(origin <> "/climbs/" <> &1.projection["slug"])) ++
      Enum.map(standing_results(nil), &Projection.entry_url(&1, origin))
  end

  defp standing_results(before) do
    %{entries: entries, next_before_sequence: next} =
      Network.Query.page(before_sequence: before, limit: Network.maximum_page_size())

    standing = Enum.reject(entries, &Network.Query.withdrawn?/1)

    if next, do: standing ++ standing_results(next), else: standing
  end

  defp document(urls) do
    entries = Enum.map_join(urls, "\n", &"  <url><loc>#{Plug.HTML.html_escape(&1)}</loc></url>")

    ~s(<?xml version="1.0" encoding="UTF-8"?>\n) <>
      ~s(<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n) <>
      entries <> "\n</urlset>\n"
  end
end
