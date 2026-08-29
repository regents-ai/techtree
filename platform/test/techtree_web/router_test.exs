defmodule TechtreeWeb.RouterTest do
  @moduledoc """
  The routing table is part of the product promise: this application publishes,
  and accepts one thing at one address and nothing else anywhere. These tests
  read the table itself rather than trusting that nobody added a route, and
  they check the refusals a curious caller would actually attempt.

  The table carries exactly one write, and it is named here, in
  `TechtreeWeb.MethodSurface`, and in the router's own documentation, so that a
  reader who finds one finds the other two. `POST /api/v1/publications` is where
  a participant publishes a finished run and where the same participant later
  withdraws one — two documents at one address, told apart by what each declares
  itself to be rather than by the URL. A second write appearing without those
  three places changing together is the failure these tests exist to catch.

  The path parameters are pinned as well. A run is addressed by its bundle
  digest, a key by its own fingerprint, and a Climb by a slug the catalog can
  resolve — and nothing else may become a path parameter without this list
  being changed on purpose.
  """

  use TechtreeWeb.ConnCase, async: true

  @routes TechtreeWeb.Router.__routes__()

  test "exactly one route is a write, and it is where a participant's own run goes" do
    writes =
      @routes
      |> Enum.reject(&(&1.verb == :get))
      |> Enum.map(&"#{&1.verb} #{&1.path}")

    assert writes == ["post /api/v1/publications"]
  end

  # Previews of work heading for `/`, compiled only where `dev_routes` is set:
  # this suite and the development server, never a release. Founder ruling
  # 2026-08-28 - they are for him to look at and they are not v0.1 routes.
  # Hand-maintained on purpose. A preview that appears without being named here
  # fails the test below, which is the point: adding one is somebody saying
  # "this is a preview, not a route", rather than a route quietly becoming
  # exempt from the pin by being written in the right place.
  @previews [
    "get /crown/1",
    "get /crown/2",
    "get /crown/3",
    "get /crown/4",
    "get /prism"
  ]

  test "the previews are exactly the studies and reference the founder asked for" do
    paths = @routes |> Enum.map(&"#{&1.verb} #{&1.path}") |> Enum.sort()

    assert Enum.sort(@previews) == Enum.filter(paths, &(&1 in @previews)),
           "a preview named here is missing, or one is here that should not be"
  end

  test "every preview is declared inside the guard that keeps it out of a release" do
    source = File.read!("lib/techtree_web/router.ex")

    [_before, guarded] =
      String.split(source, "if Application.compile_env(:techtree, :dev_routes) do", parts: 2)

    for preview <- @previews do
      path = preview |> String.split(" ") |> List.last()
      declaration = ~s(live "#{path}")

      assert String.contains?(guarded, declaration),
             "#{path} is not declared inside the dev_routes guard"

      assert source |> String.split(declaration) |> length() == 2,
             "#{path} is declared more than once, so one of them escapes the guard"
    end
  end

  test "the routing table is exactly the published surface" do
    paths =
      @routes
      |> Enum.map(&"#{&1.verb} #{&1.path}")
      |> Enum.reject(&(&1 in @previews))
      |> Enum.sort()

    assert paths == [
             "get /",
             "get /api/v1/bootstrap",
             "get /api/v1/catalog",
             "get /api/v1/climbs/:slug",
             "get /api/v1/objects/:digest",
             "get /api/v1/publication-keys/:key_id",
             "get /api/v1/publications",
             "get /api/v1/publications/:bundle_digest",
             "get /climbs/:slug",
             "get /docs",
             "get /healthz",
             "get /proofs",
             "get /results",
             "get /results/:bundle_digest",
             "get /skill.md",
             "get /start",
             "post /api/v1/publications"
           ]
  end

  test "no route takes a path parameter other than a digest, a fingerprint or a slug" do
    parameters =
      @routes
      |> Enum.reject(&("#{&1.verb} #{&1.path}" in @previews))
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
