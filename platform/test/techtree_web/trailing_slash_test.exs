defmodule TechtreeWeb.TrailingSlashTest do
  # Regression: the router matched /about/ and //about as /about, and the page
  # then looked up its document under the address as sent and crashed. ConnCase
  # for the homepage, which reads the catalog.
  use TechtreeWeb.ConnCase, async: true

  test "a page address with a slash at the end is the site's not-found page" do
    for path <- ["/about/", "/terms/", "/wallet-bench/", "/llms.txt/"] do
      response = request(path, "text/html")
      assert response.status == 404
      assert response.resp_body =~ "We can’t find that page"
    end
  end

  test "an API address with a slash at the end is the API's not-found answer" do
    response = request("/api/v1/profile/", "*/*")
    assert response.status == 404
    assert [content_type] = get_resp_header(response, "content-type")
    assert content_type =~ "application/json"
    assert %{"error" => %{"code" => "not_found"}} = Jason.decode!(response.resp_body)
  end

  test "a page address with an empty segment is the site's not-found page" do
    # The router matches //about as /about.
    {404, _headers, body} =
      assert_error_sent(404, fn ->
        request(%{Plug.Test.conn(:get, "/about") | request_path: "//about"}, "text/html")
      end)

    assert body =~ "We can’t find that page"
  end

  test "the homepage keeps its slash" do
    assert request("/", "text/html").status == 200
  end

  defp request(path, accept) when is_binary(path), do: request(Plug.Test.conn(:get, path), accept)

  defp request(conn, accept) do
    conn
    |> put_req_header("accept", accept)
    |> TechtreeWeb.Endpoint.call(TechtreeWeb.Endpoint.init([]))
  end
end
