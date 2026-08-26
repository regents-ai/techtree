defmodule TechtreeWeb.SkillControllerTest do
  @moduledoc """
  The agent-readable installation page. Same facts as the pages a person
  reads, same source, and the same refusal to describe a release that is not
  being served.
  """

  use TechtreeWeb.ConnCase, async: false

  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture
  alias TechtreeWeb.ReleaseInfo

  @tag :tmp_dir
  test "it derives from the release being served", %{conn: conn, tmp_dir: tmp_dir} do
    bundle = CatalogFixture.copy!(tmp_dir)
    CatalogFixture.rewrite_bootstrap!(bundle, &CatalogFixture.concrete_release/1)
    CatalogFixture.use_bundle(bundle)
    Importer.import!(bundle)
    release = ReleaseInfo.current()

    conn = get(conn, ~p"/skill.md")

    assert response(conn, 200) =~ "# Techtree 0.1.0"
    assert conn.resp_body =~ "uv tool install --python 3.12 techtree==0.1.0"
    assert conn.resp_body =~ release.digest
    assert conn.resp_body =~ release.source_revision
    assert conn.resp_body =~ "techtree doctor --climb hello-world-climb@1"
    assert conn.resp_body =~ "macOS or Linux · Python 3.12, provided by the installer"

    assert conn.resp_body =~
             "The agent under test still makes model calls, and those go to the model provider"

    refute conn.resp_body =~ ~r/\btechtree up\b/
    assert get_resp_header(conn, "content-type") == ["text/markdown; charset=utf-8"]
  end

  test "a stand-in release is not emitted as installation metadata", %{conn: conn} do
    CatalogFixture.use_bundle(CatalogFixture.root())
    Importer.import!(CatalogFixture.root())

    conn = get(conn, ~p"/skill.md")

    assert response(conn, 404) == "No concrete Techtree release is active on this channel.\n"
    refute conn.resp_body =~ "placeholder"
  end

  test "nothing published at all is the same refusal", %{conn: conn} do
    CatalogFixture.use_bundle(CatalogFixture.root())

    conn = get(conn, ~p"/skill.md")

    assert response(conn, 404) =~ "No concrete Techtree release is active on this channel."
  end
end
