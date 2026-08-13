defmodule TechtreeWeb.HealthControllerTest do
  use TechtreeWeb.ConnCase, async: false

  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture

  test "an application with no active release is not healthy", %{conn: conn} do
    CatalogFixture.use_bundle(CatalogFixture.root())

    conn = get(conn, ~p"/healthz")

    assert conn.status == 503
    body = json_response(conn, 503)
    assert body["status"] == "unavailable"
    assert body["catalog_import_status"] == "none"
    assert body["channel"] == "development"
  end

  describe "with a release being served" do
    setup do
      CatalogFixture.use_bundle(CatalogFixture.root())
      %{release: Importer.import!(CatalogFixture.root())}
    end

    test "health names the release being served", %{conn: conn, release: release} do
      conn = get(conn, ~p"/healthz")

      assert conn.status == 200
      body = json_response(conn, 200)

      assert body["status"] == "ok"
      assert body["catalog_import_status"] == "complete"
      assert body["channel"] == "development"
      assert body["catalog_digest"] == release.catalog_digest
      assert body["source_revision"] == release.source_revision
      assert body["climb_count"] == 1
      assert get_resp_header(conn, "cache-control") == ["no-store"]
    end

    test "health describes the catalog, never the machine", %{conn: conn} do
      body = conn |> get(~p"/healthz") |> response(200) |> String.downcase()

      for leak <- [
            String.downcase(CatalogFixture.root()),
            "/users",
            "postgres",
            "database_url",
            "secret",
            "localhost"
          ] do
        refute body =~ leak
      end
    end
  end
end
