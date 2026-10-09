defmodule TechtreeWeb.PublicPagesController do
  @moduledoc """
  About, Contact, Privacy and Terms as pages, and the files agents and crawlers
  read first: the agent guide at `/llms.txt`, the OpenAPI description, the tool
  manifest, `robots.txt`, `security.txt` and the API catalog. All of them come
  from `TechtreeWeb.PublicDocuments`, `TechtreeWeb.OpenAPI` and
  `Techtree.Capabilities`, none reads the database, and the pages' Markdown is
  answered before the router.
  """

  use TechtreeWeb, :controller

  alias TechtreeWeb.PublicDocuments

  def show(conn, _params) do
    page = PublicDocuments.page(conn.request_path)
    render(conn, :show, page: page, page_title: page.title)
  end

  def agents(conn, _params) do
    %{markdown: text} = TechtreeWeb.PublicDocuments.document("/agents.md")
    conn |> put_resp_content_type("text/markdown") |> send_resp(200, text)
  end

  def llms(conn, _params) do
    body = PublicDocuments.llms()
    conn |> cached(body) |> put_resp_content_type("text/plain") |> send_resp(200, body)
  end

  def robots(conn, _params) do
    body = PublicDocuments.robots()
    conn |> cached(body) |> put_resp_content_type("text/plain") |> send_resp(200, body)
  end

  def security(conn, _params) do
    body = PublicDocuments.security_txt()
    conn |> cached(body) |> put_resp_content_type("text/plain") |> send_resp(200, body)
  end

  def openapi(conn, _params) do
    body = Jason.encode!(TechtreeWeb.OpenAPI.document())
    conn |> cached(body) |> put_resp_content_type("application/json") |> send_resp(200, body)
  end

  def capabilities(conn, _params) do
    body = Jason.encode!(Techtree.Capabilities.manifest())
    conn |> cached(body) |> put_resp_content_type("application/json") |> send_resp(200, body)
  end

  # A linkset with the RFC 9727 profile, which Sobelow does not read as a safe
  # content type; the body is JSON built from this site's own addresses.
  # sobelow_skip ["XSS.SendResp"]
  def api_catalog(conn, _params) do
    body = Jason.encode!(PublicDocuments.api_catalog())

    conn
    |> cached(body)
    |> put_resp_content_type(
      ~s(application/linkset+json; profile="https://www.rfc-editor.org/info/rfc9727"),
      nil
    )
    |> send_resp(200, body)
  end

  # These change only with a release: a sha256 entity tag of the body and a
  # five-minute public cache, as the template sends them.
  defp cached(conn, body) do
    conn
    |> put_resp_header("etag", ~s("#{Base.encode16(:crypto.hash(:sha256, body), case: :lower)}"))
    |> put_resp_header("cache-control", "public, max-age=300")
  end
end
