defmodule TechtreeWeb.ClimbControllerTest do
  use TechtreeWeb.ConnCase, async: false

  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture

  describe "with a release being served" do
    setup do
      CatalogFixture.use_bundle(CatalogFixture.root())
      Importer.import!(CatalogFixture.root())
      :ok
    end

    test "a Climb is summarized for choosing between Climbs", %{conn: conn} do
      summary = conn |> get(~p"/api/v1/climbs/procedure-transfer-dev") |> json_response(200)

      assert summary["kind"] == "climb_summary_projection"
      assert summary["reference"] == CatalogFixture.climb_reference()
      assert summary["title"] == "Procedure Transfer Development Climb"
      assert summary["status"] == "development"
      assert summary["purpose"] == "component_uplift"
      assert summary["task_count"] == 36
      assert summary["subject_harness"] == "hermes-agent"
      assert summary["proof_grade"] == "development_only"
      assert summary["leaderboard_enabled"] == false
      assert summary["mutation_contract"]["kind"] == "skill_insertion"

      assert summary["data_policy"] == %{
               "raw_episode_server_upload" => "prohibited",
               "raw_episode_training_use" => "prohibited",
               "candidate_skill_public_release" => "required_for_climb",
               "uplift_report_visibility" => "public"
             }
    end

    test "the summary does not pose as a protocol object", %{conn: conn} do
      summary = conn |> get(~p"/api/v1/climbs/procedure-transfer-dev") |> json_response(200)

      refute Map.has_key?(summary, "schema_version")
      refute Map.has_key?(summary, "campaign")
      refute Map.has_key?(summary, "climb")
    end

    test "the linked objects resolve to the exact protocol bytes", %{conn: conn} do
      summary = conn |> get(~p"/api/v1/climbs/procedure-transfer-dev") |> json_response(200)

      assert Map.keys(summary["objects"]) |> Enum.sort() == [
               "campaign",
               "climb",
               "data_policy",
               "taskset_validation"
             ]

      for {_name, link} <- summary["objects"] do
        assert link["media_type"] == "application/json"
        assert link["url"] == "/api/v1/objects/" <> link["digest"]

        linked = get(conn, link["url"])

        assert linked.status == 200
        assert Techtree.Catalog.Digest.hash_bytes(linked.resp_body) == link["digest"]
      end

      assert summary["objects"]["campaign"]["digest"] == CatalogFixture.campaign_digest()
      assert summary["objects"]["climb"]["digest"] == CatalogFixture.climb_digest()
    end

    test "a slug that names no Climb is not found", %{conn: conn} do
      conn = get(conn, ~p"/api/v1/climbs/no-such-climb")

      assert conn.status == 404
      assert json_response(conn, 404)["error"]["code"] == "catalog_object_missing"
    end

    test "a slug is never treated as a path", %{conn: conn} do
      for slug <- ["..%2F..%2Fetc%2Fpasswd", "procedure-transfer-dev%00", "%2E%2E"] do
        conn = get(conn, "/api/v1/climbs/#{slug}")

        assert conn.status == 404
        refute conn.resp_body =~ "/Users"
      end
    end
  end

  describe "before anything is imported" do
    setup do
      CatalogFixture.use_bundle(CatalogFixture.root())
    end

    test "no Climb resolves", %{conn: conn} do
      assert get(conn, ~p"/api/v1/climbs/procedure-transfer-dev").status == 404
    end
  end
end
