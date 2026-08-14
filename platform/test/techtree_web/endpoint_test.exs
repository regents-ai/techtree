defmodule TechtreeWeb.EndpointTest do
  @moduledoc """
  What the pipeline in front of the routing table will and will not do.

  The routing table already says this application only publishes. These tests
  are about the part before it: a caller who sends something no route asks for
  should meet a refusal without the server having read a file, written one to
  disk, or let a hidden parameter rewrite the verb it will be judged by.
  """

  use TechtreeWeb.ConnCase, async: true

  @multipart_boundary "techtreetestboundary"

  describe "a body no route asked for" do
    test "a file in a multipart body is never read into a parameter", %{conn: conn} do
      conn =
        conn
        |> put_req_header(
          "content-type",
          "multipart/form-data; boundary=#{@multipart_boundary}"
        )
        |> post("/api/v1/nope", multipart_file("skill", "SKILL.md", "an uploaded skill"))

      assert conn.status == 404
      refute Map.has_key?(conn.params, "skill")
      refute conn.params |> Map.values() |> Enum.any?(&match?(%Plug.Upload{}, &1))
    end

    test "a multipart body to a published address is refused the same way", %{conn: conn} do
      conn =
        conn
        |> put_req_header(
          "content-type",
          "multipart/form-data; boundary=#{@multipart_boundary}"
        )
        |> post("/api/v1/catalog", multipart_file("skill", "SKILL.md", "an uploaded skill"))

      assert conn.status == 404
      refute Map.has_key?(conn.params, "skill")
    end

    test "the body is left unread rather than parsed", %{conn: conn} do
      conn =
        conn
        |> put_req_header(
          "content-type",
          "multipart/form-data; boundary=#{@multipart_boundary}"
        )
        |> post("/api/v1/nope", multipart_file("skill", "SKILL.md", "an uploaded skill"))

      # Parsing is the only thing that would spool a file to disk, and the body
      # was not merely left unparsed: it was never fetched at all.
      assert conn.body_params == %Plug.Conn.Unfetched{aspect: :body_params}
    end
  end

  describe "the verb a request is judged by" do
    test "a hidden parameter cannot rewrite it", %{conn: conn} do
      conn =
        conn
        |> put_req_header("content-type", "application/x-www-form-urlencoded")
        |> post("/api/v1/catalog", "_method=DELETE")

      assert conn.method == "POST"
      assert conn.status == 404
    end

    test "a query parameter cannot rewrite it either", %{conn: conn} do
      conn =
        conn
        |> put_req_header("content-type", "application/x-www-form-urlencoded")
        |> post("/api/v1/catalog?_method=DELETE", "")

      assert conn.method == "POST"
      assert conn.status == 404
    end
  end

  describe "a static file" do
    test "is served with the refusals a page is served with", %{conn: conn} do
      for path <- ["/robots.txt", "/favicon.ico", "/assets/css/app.css"] do
        served = get(conn, path)

        assert served.status == 200, "#{path} is not being served"

        assert get_resp_header(served, "content-security-policy") == [
                 "default-src 'none'; frame-ancestors 'none'"
               ],
               "#{path} carries no content policy"

        assert get_resp_header(served, "x-content-type-options") == ["nosniff"]
        assert get_resp_header(served, "x-frame-options") == ["DENY"]
        assert get_resp_header(served, "referrer-policy") == ["no-referrer"]
      end
    end

    test "outside the published list is not served at all", %{conn: conn} do
      for path <- ["/../mix.exs", "/priv/catalog/catalog.json", "/lib/techtree.ex"] do
        assert get(conn, path).status == 404
      end
    end
  end

  # One field of a multipart body, spelled out, so the test does not depend on
  # a helper that might encode it some other way.
  defp multipart_file(name, filename, contents) do
    """
    --#{@multipart_boundary}\r
    content-disposition: form-data; name="#{name}"; filename="#{filename}"\r
    content-type: text/markdown\r
    \r
    #{contents}\r
    --#{@multipart_boundary}--\r
    """
  end
end
