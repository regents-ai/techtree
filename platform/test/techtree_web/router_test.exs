defmodule TechtreeWeb.RouterTest do
  @moduledoc """
  Pins the published route surface and method refusals. Private profile writes
  are distinct from publication documents and retain independent authorization.
  """

  use TechtreeWeb.ConnCase, async: true

  @routes TechtreeWeb.Router.__routes__()

  test "writes are limited to publication and private profile actions" do
    writes =
      @routes
      |> Enum.reject(&(&1.verb == :get))
      |> Enum.map(&"#{&1.verb} #{&1.path}")

    assert Enum.sort(writes) == [
             "patch /api/v1/profile",
             "post /api/v1/profile/sync",
             "post /api/v1/publications"
           ]
  end

  test "the routing table is exactly the published surface" do
    paths =
      @routes
      |> Enum.map(&"#{&1.verb} #{&1.path}")
      |> Enum.sort()

    assert paths == [
             "get /",
             "get /api/v1/bootstrap",
             "get /api/v1/catalog",
             "get /api/v1/climbs/:slug",
             "get /api/v1/objects/:digest",
             "get /api/v1/profile",
             "get /api/v1/publication-keys/:key_id",
             "get /api/v1/publications",
             "get /api/v1/publications/:bundle_digest",
             "get /api/v1/publications/:bundle_digest/bundle",
             "get /blog",
             "get /blog/:slug",
             "get /changelog",
             "get /climbs/:slug",
             "get /docs",
             "get /healthz",
             "get /proofs",
             "get /repo2rlenv",
             "get /results",
             "get /results/:bundle_digest",
             "get /skill.md",
             "get /start",
             "get /verify",
             "patch /api/v1/profile",
             "post /api/v1/profile/sync",
             "post /api/v1/publications"
           ]
  end

  test "no route takes a path parameter other than a digest, a fingerprint or a slug" do
    parameters =
      @routes
      |> Enum.flat_map(&Regex.scan(~r/:([a-z_]+)/, &1.path, capture: :all_but_first))
      |> List.flatten()
      |> Enum.uniq()
      |> Enum.sort()

    assert parameters == ["bundle_digest", "digest", "key_id", "slug"]
  end

  test "no artifact, proof, bundle, or login route exists", %{conn: conn} do
    for path <- [
          "/api/v1/artifacts",
          "/api/v1/proofs",
          "/api/v1/results",
          "/api/v1/bundles",
          "/api/v1/submissions",
          "/api/v1/publication-withdrawals",
          "/api/v1/network-key",
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
          "/proofs",
          "/results",
          "/results/sha256:#{String.duplicate("a", 64)}",
          "/skill.md",
          "/start",
          "/climbs/hello-world-climb",
          "/healthz",
          "/api/v1/catalog",
          "/api/v1/bootstrap",
          "/api/v1/climbs/hello-world-climb",
          "/api/v1/objects/sha256:#{String.duplicate("a", 64)}",
          "/api/v1/publications/sha256:#{String.duplicate("a", 64)}",
          "/api/v1/publications/sha256:#{String.duplicate("a", 64)}/bundle",
          "/api/v1/publication-keys/sha256:#{String.duplicate("a", 64)}"
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

  test "the one write address refuses every method but the ones it answers", %{conn: conn} do
    path = "/api/v1/publications"

    for refused <- [put(conn, path, %{}), patch(conn, path, %{}), delete(conn, path)] do
      assert refused.status == 405
      assert get_resp_header(refused, "allow") == ["GET, HEAD, POST"]

      assert %{"error" => %{"message" => message}} = json_response(refused, 405)
      assert message == "this address accepts one kind of signed document, and nothing else"
    end
  end

  test "an address this release does not publish stays a 404", %{conn: conn} do
    for path <- [
          "/api/v1/nope",
          "/campaigns",
          "/campaigns/hello-world-climb",
          "/climbs",
          "/climbs/no-such-climb/edit",
          "/proofs/local",
          "/protocol",
          "/research",
          "/upload"
        ] do
      assert post(conn, path, %{}).status == 404
      assert delete(conn, path).status == 404
      assert get(conn, path).status == 404
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
