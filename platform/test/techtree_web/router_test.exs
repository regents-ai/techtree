defmodule TechtreeWeb.RouterTest do
  @moduledoc """
  The routing table is part of the product promise: this application publishes
  and does nothing else. These tests read the table itself rather than trusting
  that nobody added a route, and they check the refusals a curious caller would
  actually attempt.
  """

  use TechtreeWeb.ConnCase, async: true

  @routes TechtreeWeb.Router.__routes__()

  test "every route is a read" do
    verbs = @routes |> Enum.map(& &1.verb) |> Enum.uniq()

    assert verbs == [:get]
  end

  test "the routing table is exactly the published surface" do
    paths = @routes |> Enum.map(&"#{&1.verb} #{&1.path}") |> Enum.sort()

    assert paths == [
             "get /",
             "get /api/v1/bootstrap",
             "get /api/v1/catalog",
             "get /api/v1/climbs/:slug",
             "get /api/v1/objects/:digest",
             "get /campaigns",
             "get /campaigns/:slug",
             "get /climbs",
             "get /climbs/:slug",
             "get /docs",
             "get /healthz",
             "get /proofs",
             "get /proofs/:digest",
             "get /proofs/local",
             "get /protocol",
             "get /skill.md",
             "get /start"
           ]
  end

  test "no route takes a path parameter other than a digest or a slug" do
    parameters =
      @routes
      |> Enum.flat_map(&Regex.scan(~r/:([a-z_]+)/, &1.path, capture: :all_but_first))
      |> List.flatten()
      |> Enum.uniq()
      |> Enum.sort()

    assert parameters == ["digest", "slug"]
  end

  test "no submission, artifact, proof, run, or login route exists", %{conn: conn} do
    for path <- [
          "/api/v1/submissions",
          "/api/v1/artifacts",
          "/api/v1/proofs",
          "/api/v1/runs",
          "/api/v1/login",
          "/api/v1/skills",
          "/api/v1/receipts",
          "/api/v1/leaderboard"
        ] do
      assert post(conn, path, %{}).status == 404
      assert get(conn, path).status == 404
    end
  end

  test "a published address answers a mutating method with 405, not 404", %{conn: conn} do
    for path <- [
          "/",
          "/docs",
          "/campaigns",
          "/campaigns/hello-world-climb",
          "/start",
          "/climbs",
          "/climbs/hello-world-climb",
          "/proofs",
          "/proofs/sha256:#{String.duplicate("a", 64)}",
          "/proofs/local",
          "/protocol",
          "/skill.md",
          "/healthz",
          "/api/v1/catalog",
          "/api/v1/bootstrap",
          "/api/v1/climbs/hello-world-climb",
          "/api/v1/objects/sha256:#{String.duplicate("a", 64)}"
        ] do
      for refused <- [
            post(conn, path, %{}),
            put(conn, path, %{}),
            patch(conn, path, %{}),
            delete(conn, path)
          ] do
        assert refused.status == 405, "#{refused.method} #{path} answered #{refused.status}"
        assert get_resp_header(refused, "allow") == ["GET, HEAD"]

        assert %{"error" => %{"code" => "method_not_allowed", "retryable" => false}} =
                 json_response(refused, 405)
      end
    end
  end

  test "an address this release does not publish stays a 404", %{conn: conn} do
    for path <- ["/api/v1/nope", "/climbs/no-such-climb/edit", "/upload"] do
      assert post(conn, path, %{}).status == 404
      assert delete(conn, path).status == 404
      assert get_resp_header(post(conn, path, %{}), "allow") == []
    end
  end

  test "an unknown route is refused in the shared error shape", %{conn: conn} do
    conn =
      conn
      |> put_req_header("accept", "application/json")
      |> get("/api/v1/nope")

    assert conn.status == 404
    assert %{"error" => %{"code" => "not_found", "retryable" => false}} = json_response(conn, 404)
  end
end
