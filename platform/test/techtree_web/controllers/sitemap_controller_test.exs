defmodule TechtreeWeb.SitemapControllerTest do
  use TechtreeWeb.ConnCase, async: false

  test "the blog has no page and no sitemap entry while it has no post", %{conn: conn} do
    assert TechtreeWeb.Blog.all() == []
    assert conn |> get(~p"/blog") |> html_response(404) =~ "Blog"
    refute conn |> get(~p"/sitemap.xml") |> response(200) =~ "/blog"
  end

  test "the motion lab is gone from the site and the sitemap with the showcase off", %{conn: conn} do
    previous = Application.fetch_env!(:techtree, :showcase)
    Application.put_env(:techtree, :showcase, :off)
    on_exit(fn -> Application.put_env(:techtree, :showcase, previous) end)

    assert {404, _headers, _body} = assert_error_sent(404, fn -> get(conn, "/animations") end)
    refute conn |> get(~p"/sitemap.xml") |> response(200) =~ "/animations"
  end
end
