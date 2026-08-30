defmodule TechtreeWeb.CatalogControllerTest do
  use TechtreeWeb.ConnCase, async: false

  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture

  describe "with a release being served" do
    setup do
      CatalogFixture.use_bundle(CatalogFixture.root())
      Importer.import!(CatalogFixture.root())
      :ok
    end

    test "the index is served as the bytes techtree-python generated", %{conn: conn} do
      conn = get(conn, ~p"/api/v1/catalog")

      assert conn.status == 200
      assert conn.resp_body == CatalogFixture.read!(CatalogFixture.root(), "catalog.json")
      assert get_resp_header(conn, "content-type") == ["application/json"]
    end

    test "the index is briefly cacheable and tagged with its digest", %{conn: conn} do
      conn = get(conn, ~p"/api/v1/catalog")

      assert get_resp_header(conn, "cache-control") == ["public, max-age=300"]
      assert get_resp_header(conn, "etag") == [~s("#{CatalogFixture.catalog_digest()}")]
      assert get_resp_header(conn, "x-content-type-options") == ["nosniff"]

      assert get_resp_header(conn, "content-security-policy") == [
               "default-src 'none'; frame-ancestors 'none'"
             ]
    end

    test "a caller holding the index digest is told nothing changed", %{conn: conn} do
      conn =
        conn
        |> put_req_header("if-none-match", ~s("#{CatalogFixture.catalog_digest()}"))
        |> get(~p"/api/v1/catalog")

      assert conn.status == 304
      assert conn.resp_body == ""
    end

    test "a caller holding a different digest is served the index", %{conn: conn} do
      conn =
        conn
        |> put_req_header("if-none-match", ~s("sha256:#{String.duplicate("a", 64)}"))
        |> get(~p"/api/v1/catalog")

      assert conn.status == 200
    end
  end

  describe "before anything is imported" do
    setup do
      CatalogFixture.use_bundle(CatalogFixture.root())
    end

    test "the index is answered as unavailable, and says why", %{conn: conn} do
      conn = get(conn, ~p"/api/v1/catalog")

      assert conn.status == 503
      assert json_response(conn, 503)["error"]["code"] == "bootstrap_release_missing"
    end
  end
end
