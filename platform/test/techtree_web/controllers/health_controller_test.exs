defmodule TechtreeWeb.HealthControllerTest do
  use TechtreeWeb.ConnCase, async: false

  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture

  test "an application with no active release is not healthy", %{conn: conn} do
    CatalogFixture.use_bundle(CatalogFixture.root())

    conn = get(conn, ~p"/healthz")

    assert response(conn, 503) == "unavailable"
    assert response_content_type(conn, :txt) =~ "text/plain"
  end

  test "an application serving a release answers ok", %{conn: conn} do
    CatalogFixture.use_bundle(CatalogFixture.root())
    Importer.import!(CatalogFixture.root())

    conn = get(conn, ~p"/healthz")

    assert response(conn, 200) == "ok"
    assert response_content_type(conn, :txt) =~ "text/plain"
    assert get_resp_header(conn, "cache-control") == ["no-store"]
  end

  test "the JSON health check answers 503 unavailable with no active release", %{conn: conn} do
    CatalogFixture.use_bundle(CatalogFixture.root())

    conn = get(conn, ~p"/api/v1/health")

    assert %{"error" => %{"code" => "unavailable", "message" => _, "hint" => _}} =
             json_response(conn, 503)

    assert get_resp_header(conn, "cache-control") == ["no-store"]
  end

  test "the JSON health check answers status ok while a release is served", %{conn: conn} do
    CatalogFixture.use_bundle(CatalogFixture.root())
    Importer.import!(CatalogFixture.root())

    conn = get(conn, ~p"/api/v1/health")

    assert json_response(conn, 200) == %{"status" => "ok"}
    assert get_resp_header(conn, "cache-control") == ["no-store"]
    assert [~s("default";q=) <> _] = get_resp_header(conn, "ratelimit-policy")
  end
end
