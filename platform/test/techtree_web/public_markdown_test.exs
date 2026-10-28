defmodule TechtreeWeb.PublicMarkdownTest do
  @moduledoc """
  Every public page answers `Accept: text/markdown` at its own address, and its
  HTML says so in the head. The release named in the agent documents is the one
  being served, never a number written by hand.
  """

  use TechtreeWeb.ConnCase, async: false

  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture
  alias Techtree.NetworkFixture
  alias Techtree.WalletBenchFixture
  alias TechtreeWeb.PublicDocuments
  alias TechtreeWeb.ReleaseInfo

  @pages [
           "/",
           "/about",
           "/contact",
           "/privacy",
           "/terms",
           "/docs",
           "/changelog",
           "/verify",
           "/repo2rlenv",
           "/services/verify",
           "/services/verify/sample-report",
           "/services/cyber-assist",
           "/services/cyber-assist/sample-report",
           "/start",
           "/results",
           "/results/" <> NetworkFixture.bundle_digest(),
           "/climbs/hello-world-climb",
           "/examples/tdd",
           "/wallet-bench"
         ] ++ Enum.map(TechtreeWeb.DocsGuides.slugs(), &("/docs/" <> &1))

  @moduletag :tmp_dir

  setup %{tmp_dir: tmp_dir} do
    bundle = CatalogFixture.copy!(tmp_dir)
    CatalogFixture.rewrite_bootstrap!(bundle, &CatalogFixture.concrete_release/1)
    CatalogFixture.use_bundle(bundle)
    Importer.import!(bundle)
    {:ok, _entry, :recorded} = NetworkFixture.publish()
    WalletBenchFixture.seed!()
    :ok
  end

  test "every public page answers Markdown at its own address", %{conn: conn} do
    assert_markdown(conn, @pages)
  end

  test "Start and the short start still answer with no release being served", %{conn: conn} do
    CatalogFixture.use_bundle(CatalogFixture.root())
    Importer.import!(CatalogFixture.root())

    assert_markdown(conn, ["/start"])
    assert conn |> get(~p"/llms.txt") |> response(200) =~ ~r/\A# Techtree\n/
  end

  test "every public page's HTML points to its Markdown, the sitemap and the API", %{conn: conn} do
    for path <- @pages do
      html = conn |> get(path) |> html_response(200)
      canonical = TechtreeWeb.Endpoint.url() <> path

      assert html =~ ~s(<link rel="alternate" type="text/markdown" href="#{canonical}">), path
      assert html =~ ~s(rel="sitemap"), path
      assert html =~ ~s(rel="service-desc"), path
    end
  end

  test "a page without Markdown does not claim one", %{conn: conn} do
    [attempt | _attempts] = Techtree.WalletBench.list_attempts!()
    html = conn |> get(~p"/wallet-bench/#{attempt.id}") |> html_response(200)

    refute html =~ ~s(type="text/markdown")
  end

  test "a Result that was never published is a Markdown 404", %{conn: conn} do
    {404, headers, _body} =
      assert_error_sent(404, fn ->
        conn
        |> put_req_header("accept", "text/markdown")
        |> get("/results/sha256:" <> String.duplicate("0", 64))
      end)

    assert {"content-type", "text/markdown; charset=utf-8"} in headers
  end

  test "the agent documents name only the release being served", %{conn: conn} do
    release = ReleaseInfo.current()
    install = Enum.join(release.install_argv, " ")

    for path <- ["/llms.txt", "/agents.md"] do
      text = conn |> get(path) |> response(200)

      assert text =~ install, path

      for [_match, version] <- Regex.scan(~r/(?:regents-cli |==)v?(\d+\.\d+\.\d+)/, text) do
        assert version == release.version, path
      end
    end
  end

  test "the short start for agents stays short and says the payment once", %{conn: conn} do
    text = conn |> get(~p"/llms.txt") |> response(200)

    assert byte_size(text) < 3 * 1024
    assert length(String.split(text, PublicDocuments.payment())) == 2

    agents = conn |> get(~p"/agents.md") |> response(200)
    assert length(String.split(agents, PublicDocuments.payment())) == 2
  end

  defp assert_markdown(conn, paths) do
    for path <- paths do
      response = conn |> put_req_header("accept", "text/markdown") |> get(path)

      assert response.status == 200, path
      assert [content_type] = get_resp_header(response, "content-type")
      assert content_type =~ "text/markdown", path
      assert response.resp_body =~ ~r/\A# \S/, path
      refute response.resp_body =~ "data-phx-main", path
    end
  end
end
