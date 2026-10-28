defmodule TechtreeWeb.PublicPagesController do
  @moduledoc """
  About, Contact, Privacy, Terms and the two sample reports under `/services`
  as pages, and the files agents and crawlers read first: the short start for
  agents at `/llms.txt`, the OpenAPI
  description, the tool manifest, `robots.txt`, `security.txt`, the API
  catalog, the Techtree skill at `/skill.md`, each agent's own skill at
  `/agents/SLUG/skill.md` and the skills index under `/.well-known/agent-skills`.
  All of them come from `TechtreeWeb.PublicDocuments`, `TechtreeWeb.OpenAPI`,
  `Techtree.Capabilities`, `TechtreeWeb.AgentSkills` and
  `TechtreeWeb.AgentGuides`; only `/llms.txt` reads the
  database, for the install line of the release being served. The pages'
  Markdown is answered before the router.
  """

  use TechtreeWeb, :controller

  alias TechtreeWeb.AgentGuides
  alias TechtreeWeb.AgentSkills
  alias TechtreeWeb.PublicDocuments
  alias TechtreeWeb.ReleaseInfo

  # The router matches "//about" as "/about"; only the page's own address is that page.
  def show(conn, _params) do
    if PublicDocuments.document?(conn.request_path) do
      page = PublicDocuments.page(conn.request_path)
      render(conn, :show, page: page, page_title: page.title)
    else
      raise TechtreeWeb.NotFoundError
    end
  end

  @doc "The Techtree skill at `/skill.md`, the same file the skills index serves."
  def skill_guide(conn, _params),
    do: send_cached(conn, "text/markdown", AgentSkills.skill_guide())

  @doc "One agent's skill: the Techtree skill with that agent's Set up section added."
  def agent_skill_guide(conn, %{"agent" => slug}) do
    case AgentGuides.skill(slug) do
      nil -> raise TechtreeWeb.NotFoundError
      skill -> send_cached(conn, "text/markdown", skill)
    end
  end

  # Only the fixed table in AgentSkills answers; any other path is the site's 404.
  # The content type comes from that table too, never from the request.
  def agent_skill(conn, %{"path" => path}) do
    case AgentSkills.fetch(Enum.join(path, "/")) do
      {:ok, {type, body}} ->
        conn
        |> put_resp_header("access-control-allow-origin", "*")
        |> send_cached(type, body, if(type == "application/zip", do: nil, else: "utf-8"))

      :error ->
        raise TechtreeWeb.NotFoundError
    end
  end

  def llms(conn, _params) do
    body = PublicDocuments.llms(ReleaseInfo.current())
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

  # Every type and body comes from this site's own tables, never from the request.
  # sobelow_skip ["XSS.ContentType", "XSS.SendResp"]
  defp send_cached(conn, type, body, charset \\ "utf-8") do
    conn
    |> cached(body)
    |> put_resp_content_type(type, charset)
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
