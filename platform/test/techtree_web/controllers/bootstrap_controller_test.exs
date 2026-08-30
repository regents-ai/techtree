defmodule TechtreeWeb.BootstrapControllerTest do
  use TechtreeWeb.ConnCase, async: false

  alias Techtree.Catalog.Digest
  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture

  describe "with a release published" do
    setup do
      CatalogFixture.use_bundle(CatalogFixture.root())
      Importer.import!(CatalogFixture.root())
      :ok
    end

    test "the payload is served as the exact stored bytes", %{conn: conn} do
      conn = get(conn, ~p"/api/v1/bootstrap")

      assert conn.status == 200
      assert conn.resp_body == CatalogFixture.read!(CatalogFixture.root(), "bootstrap.json")
      assert get_resp_header(conn, "content-type") == ["application/json"]
      assert get_resp_header(conn, "cache-control") == ["public, max-age=300"]
      assert get_resp_header(conn, "etag") == [~s("#{Digest.hash_bytes(conn.resp_body)}")]
    end

    test "a caller holding the payload digest is told nothing changed", %{conn: conn} do
      digest = Digest.hash_bytes(CatalogFixture.read!(CatalogFixture.root(), "bootstrap.json"))

      conn =
        conn
        |> put_req_header("if-none-match", ~s("#{digest}"))
        |> get(~p"/api/v1/bootstrap")

      assert conn.status == 304
    end

    test "every executable instruction is an array of arguments", %{conn: conn} do
      payload = conn |> get(~p"/api/v1/bootstrap") |> json_response(200)

      argv_lists = [
        payload["cli"]["install_argv"],
        payload["hermes_plugin"]["install_argv"],
        payload["hermes_plugin"]["doctor_argv"]
      ]

      for argv <- argv_lists do
        assert is_list(argv)
        assert argv != []
        assert Enum.all?(argv, &is_binary/1)
      end

      refute Map.has_key?(payload["cli"], "install_command")
      refute Map.has_key?(payload["hermes_plugin"], "install_command")
    end

    test "the payload pins what an installer needs and nothing it does not", %{conn: conn} do
      payload = conn |> get(~p"/api/v1/bootstrap") |> json_response(200)

      assert payload["schema_version"] == "techtree.bootstrap.v1alpha1"
      assert payload["channel"] == "development"
      assert payload["minimums"]["hermes_version"] == "0.20.1"
      assert payload["minimums"]["docker_required"] == true
      assert payload["cli"]["distribution"] == "techtree"
      assert payload["cli"]["version"] =~ "placeholder"
      assert payload["hermes_plugin"]["plugin_id"] == "techtree"
      assert String.match?(payload["hermes_plugin"]["revision"], ~r/\A[0-9a-f]{40}\z/)
      assert payload["introductory_climb"]["reference"] == "hello-world-climb@1"

      assert payload["introductory_climb"]["host_prompt"] ==
               "Set up Techtree and run the Hello World Climb."
    end

    test "the payload says outright that its coordinates are placeholders", %{conn: conn} do
      payload = conn |> get(~p"/api/v1/bootstrap") |> json_response(200)

      assert payload["placeholder_release"] == true
      assert payload["cli"]["version"] == "0.0.0-placeholder"
      assert payload["cli"]["source_revision"] == String.duplicate("0", 40)
      assert payload["hermes_plugin"]["revision"] == String.duplicate("0", 40)
      assert "techtree==0.0.0-placeholder" in payload["cli"]["install_argv"]
    end

    test "the payload carries no credential", %{conn: conn} do
      body = conn |> get(~p"/api/v1/bootstrap") |> response(200) |> String.downcase()

      for secret <- ~w(api_key apikey token secret password credential authorization bearer) do
        refute body =~ secret
      end
    end

    test "the shipped development document is the one that is published", %{conn: conn} do
      body = conn |> get(~p"/api/v1/bootstrap") |> response(200)

      assert body == File.read!(Application.app_dir(:techtree, "priv/bootstrap/development.json"))
    end
  end

  describe "before anything is imported" do
    setup do
      CatalogFixture.use_bundle(CatalogFixture.root())
    end

    test "the endpoint is answered as unavailable, and says why", %{conn: conn} do
      conn = get(conn, ~p"/api/v1/bootstrap")

      assert conn.status == 503
      assert json_response(conn, 503)["error"]["code"] == "bootstrap_release_missing"
      assert get_resp_header(conn, "cache-control") == ["no-store"]
    end
  end
end
