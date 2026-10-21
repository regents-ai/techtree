defmodule TechtreeWeb.ResultShareCardControllerTest do
  @moduledoc """
  A published Result's share picture: its page names it, it is drawn at the
  size share cards use and counted against the request budget (it is drawn
  for every request), a withdrawal gives it a new address, and there is
  nothing at the address of a Result nobody published.
  """

  use TechtreeWeb.ConnCase, async: false

  alias Techtree.Catalog.Importer
  alias Techtree.CatalogFixture
  alias Techtree.NetworkFixture

  setup do
    CatalogFixture.use_bundle(CatalogFixture.root())
    Importer.import!(CatalogFixture.root())

    keys = NetworkFixture.key_pair()
    files = NetworkFixture.resign(NetworkFixture.scored(), keys: keys)
    {:ok, entry, :recorded} = NetworkFixture.publish(NetworkFixture.submission(files))

    {:ok, entry: entry, keys: keys}
  end

  test "the Result's page shares its own picture, a 1200 by 630 PNG", %{conn: conn, entry: entry} do
    image = shared_image(conn, entry)

    assert image == TechtreeWeb.Endpoint.url() <> ~p"/results/#{entry.bundle_digest}/share.png"

    response = get(conn, URI.parse(image).path)

    assert response.status == 200
    assert get_resp_header(response, "content-type") == ["image/png"]
    assert [~s("default";q=) <> _] = get_resp_header(response, "ratelimit-policy")
    assert <<137, "PNG", _::binary-size(12), 1200::32, 630::32, _::binary>> = response.resp_body
  end

  test "a withdrawn Result's picture moves to an address of its own",
       %{conn: conn, entry: entry, keys: keys} do
    published = shared_image(conn, entry)

    {:ok, _marked, :recorded} =
      NetworkFixture.withdraw(NetworkFixture.withdrawal(entry.bundle_digest, keys))

    withdrawn = shared_image(build_conn(), entry)

    refute withdrawn == published
    assert %{status: 200} = get(build_conn(), withdrawn)
  end

  test "a Result nobody published has no picture", %{conn: conn} do
    assert_error_sent 404, fn ->
      get(conn, "/results/sha256:#{String.duplicate("a", 64)}/share.png")
    end
  end

  defp shared_image(conn, entry) do
    conn
    |> get("/results/#{entry.bundle_digest}")
    |> html_response(200)
    |> LazyHTML.from_document()
    |> LazyHTML.query(~s|meta[property="og:image"]|)
    |> LazyHTML.attribute("content")
    |> then(fn [image] -> image end)
  end
end
