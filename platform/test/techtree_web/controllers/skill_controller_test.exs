defmodule TechtreeWeb.SkillControllerTest do
  use TechtreeWeb.ConnCase, async: false

  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture
  alias TechtreeWeb.ReleaseInfo

  @tag :tmp_dir
  test "the agent-readable page derives from the concrete active release", %{
    conn: conn,
    tmp_dir: tmp_dir
  } do
    bundle = CatalogFixture.copy!(tmp_dir)
    CatalogFixture.rewrite_bootstrap!(bundle, &CatalogFixture.concrete_release/1)
    CatalogFixture.use_bundle(bundle)
    Importer.import!(bundle)
    release = ReleaseInfo.current()

    conn = get(conn, ~p"/skill.md")

    assert response(conn, 200) =~ "# Techtree 0.1.0"
    assert conn.resp_body =~ "uv tool install techtree==0.1.0"
    assert conn.resp_body =~ release.digest
    assert conn.resp_body =~ release.source_revision
    assert conn.resp_body =~ "techtree doctor --climb hello-world-climb@1"
    refute conn.resp_body =~ "techtree up"
    assert get_resp_header(conn, "content-type") == ["text/markdown; charset=utf-8"]
  end

  test "a placeholder release is not emitted as installation metadata", %{conn: conn} do
    CatalogFixture.use_bundle(CatalogFixture.root())
    Importer.import!(CatalogFixture.root())

    conn = get(conn, ~p"/skill.md")

    assert response(conn, 404) == "No concrete Techtree release is active on this channel.\n"
    refute conn.resp_body =~ "placeholder"
  end
end
