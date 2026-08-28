defmodule TechtreeWeb.PublicationMetadataControllerTest do
  use TechtreeWeb.ConnCase, async: false

  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture
  alias Techtree.NetworkFixture

  setup do
    CatalogFixture.use_bundle(CatalogFixture.root())
    Importer.import!(CatalogFixture.root())
    :ok
  end

  test "passes the two metadata headers to the immutable publication projection", %{conn: conn} do
    conn =
      conn
      |> put_req_header("content-type", "application/json")
      |> put_req_header("x-techtree-skill-name", "controller-skill")
      |> put_req_header(
        "x-techtree-skill-github-url",
        "https://github.com/example/controller-skill"
      )
      |> post("/api/v1/publications", NetworkFixture.submission())

    assert conn.status == 201

    projection =
      conn
      |> recycle()
      |> get("/api/v1/publications/#{NetworkFixture.bundle_digest()}")
      |> json_response(200)

    assert projection["skill_name"] == "controller-skill"
    assert projection["skill_github_url"] == "https://github.com/example/controller-skill"
  end
end
