defmodule TechtreeWeb.ObjectControllerTest do
  use TechtreeWeb.ConnCase, async: false

  alias Techtree.Catalog.CatalogEntry
  alias Techtree.Catalog.Digest
  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture

  @unknown_digest "sha256:" <> String.duplicate("c", 64)

  describe "with a release being served" do
    setup do
      CatalogFixture.use_bundle(CatalogFixture.root())
      Importer.import!(CatalogFixture.root())
      :ok
    end

    test "every object is served as the bytes techtree-python generated", %{conn: conn} do
      for entry <- Ash.read!(CatalogEntry) do
        response = get(conn, ~p"/api/v1/objects/#{entry.protocol_digest}")

        assert response.status == 200

        assert response.resp_body ==
                 CatalogFixture.read!(CatalogFixture.root(), entry.relative_path)

        assert Digest.hash_bytes(response.resp_body) == entry.protocol_digest
      end
    end

    test "an object declares the media type the catalog recorded", %{conn: conn} do
      conn = get(conn, ~p"/api/v1/objects/#{CatalogFixture.campaign_digest()}")

      assert get_resp_header(conn, "content-type") == ["application/json"]
    end

    test "an object may be cached forever, and is tagged with its digest", %{conn: conn} do
      digest = CatalogFixture.campaign_digest()
      conn = get(conn, ~p"/api/v1/objects/#{digest}")

      assert get_resp_header(conn, "cache-control") == ["public, max-age=31536000, immutable"]
      assert get_resp_header(conn, "etag") == [~s("#{digest}")]
      assert get_resp_header(conn, "x-content-type-options") == ["nosniff"]
    end

    test "a caller holding the digest is told nothing changed", %{conn: conn} do
      digest = CatalogFixture.campaign_digest()

      conn =
        conn
        |> put_req_header("if-none-match", ~s("#{digest}"))
        |> get(~p"/api/v1/objects/#{digest}")

      assert conn.status == 304
      assert conn.resp_body == ""
    end

    test "a percent-encoded digest addresses the same object", %{conn: conn} do
      digest = CatalogFixture.campaign_digest()
      encoded = String.replace(digest, ":", "%3A")

      assert get(conn, "/api/v1/objects/#{encoded}").resp_body ==
               get(conn, ~p"/api/v1/objects/#{digest}").resp_body
    end

    test "a digest that names nothing is not found", %{conn: conn} do
      conn = get(conn, ~p"/api/v1/objects/#{@unknown_digest}")

      assert conn.status == 404
      assert %{"error" => error} = json_response(conn, 404)
      assert error["code"] == "catalog_object_missing"
    end

    test "a digest that is not a digest is a bad request", %{conn: conn} do
      for spelling <- [
            "sha256:not-a-digest",
            String.upcase(CatalogFixture.campaign_digest()),
            "sha512:" <> String.duplicate("a", 64),
            "..%2F..%2Fetc%2Fpasswd"
          ] do
        conn = get(conn, "/api/v1/objects/#{spelling}")

        assert conn.status == 400
        assert json_response(conn, 400)["error"]["code"] == "invalid_digest"
      end
    end

    test "no host path appears in a refusal", %{conn: conn} do
      body = conn |> get(~p"/api/v1/objects/#{@unknown_digest}") |> response(404)

      refute body =~ CatalogFixture.root()
      refute body =~ "/Users"
    end
  end

  describe "when the bytes on disk drifted" do
    @describetag :tmp_dir

    setup %{tmp_dir: tmp_dir} do
      bundle = CatalogFixture.copy!(tmp_dir)
      CatalogFixture.use_bundle(bundle)
      Importer.import!(bundle)

      %{bundle: bundle}
    end

    test "the object is refused rather than served", %{conn: conn, bundle: bundle} do
      CatalogFixture.write!(bundle, "campaigns/hello-world-climb.json", "{}")

      conn = get(conn, ~p"/api/v1/objects/#{CatalogFixture.campaign_digest()}")

      assert conn.status == 503
      assert json_response(conn, 503)["error"]["code"] == "catalog_object_digest_mismatch"
    end
  end

  describe "before anything is imported" do
    setup do
      CatalogFixture.use_bundle(CatalogFixture.root())
    end

    test "an object request is answered as unavailable", %{conn: conn} do
      conn = get(conn, ~p"/api/v1/objects/#{CatalogFixture.campaign_digest()}")

      assert conn.status == 503
    end
  end
end
