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
end
