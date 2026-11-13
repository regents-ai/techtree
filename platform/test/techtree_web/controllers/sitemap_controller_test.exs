defmodule TechtreeWeb.SitemapControllerTest do
  use TechtreeWeb.ConnCase, async: false

  test "the blog and each of its posts have a page and a sitemap entry", %{conn: conn} do
    [_ | _] = posts = TechtreeWeb.Blog.all()
    sitemap = conn |> get(~p"/sitemap.xml") |> response(200)

    assert conn |> get(~p"/blog") |> html_response(200) =~ "Blog"
    assert sitemap =~ "/blog<"

    for post <- posts do
      assert conn |> get(~p"/blog/#{post.slug}") |> html_response(200) =~ post.title
      assert sitemap =~ "/blog/#{post.slug}<"
    end
  end

  test "each service page and each comparison have a sitemap entry", %{conn: conn} do
    sitemap = conn |> get(~p"/sitemap.xml") |> response(200)

    for service <- TechtreeWeb.Services.all() ++ [TechtreeWeb.Services.security()] do
      assert sitemap =~ "#{TechtreeWeb.Services.path(service.id)}<"
    end

    for comparison <- Techtree.Train.Comparisons.list() do
      assert sitemap =~ "/train/#{comparison.slug}<"
    end
  end

  test "the motion lab is gone from the site and the sitemap with the showcase off", %{conn: conn} do
    previous = Application.fetch_env!(:techtree, :showcase)
    Application.put_env(:techtree, :showcase, :off)
    on_exit(fn -> Application.put_env(:techtree, :showcase, previous) end)

    assert {404, _headers, _body} = assert_error_sent(404, fn -> get(conn, "/animations") end)
    refute conn |> get(~p"/sitemap.xml") |> response(200) =~ "/animations"
  end
end
