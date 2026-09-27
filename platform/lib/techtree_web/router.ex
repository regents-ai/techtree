defmodule TechtreeWeb.Router do
  @moduledoc """
  Public catalog and signed publication routes, plus the owner-only shared
  profile. Privy profile authority never grants publication-key authority.
  """

  use TechtreeWeb, :router

  @content_security_policy "default-src 'none'; script-src 'self'; style-src 'self'; " <>
                             "img-src 'self' data:; font-src 'self'; " <>
                             "connect-src 'self' https://api.github.com; " <>
                             "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
  @theme_cookie "techtree_theme"

  # Most pages are HTML only. The home page, About, Contact and Privacy also
  # answer `Accept: text/markdown`; `TechtreeWeb.MD` holds their Markdown.
  # `/skill.md` is Markdown whichever is asked for.
  pipeline :html_only do
    plug :accepts, ["html"]
  end

  pipeline :readable do
    plug :accepts, ["html", "md"]
  end

  # The home page is a live page; its Markdown answer is sent before it mounts.
  pipeline :home_markdown do
    plug :answer_home_markdown
  end

  pipeline :browser do
    plug :fetch_session
    plug :fetch_cookies
    plug :fetch_live_flash
    plug :put_theme
    plug :put_root_layout, html: {TechtreeWeb.Layouts, :root}
    plug :protect_from_forgery

    # Browser agents may use the tools every page registers, from this site only.
    plug :put_secure_browser_headers, %{
      "content-security-policy" => @content_security_policy,
      "referrer-policy" => "no-referrer",
      "permissions-policy" => "tools=(self)"
    }
  end

  pipeline :api do
    plug :accepts, ["json"]
    plug :put_public_api_headers
  end

  # The pipeline in front of the only write the public may make; the
  # owner-only profile writes authenticate through RegentIdentity on :api.
  # Its rate limit stands in the endpoint, in front of the parser
  # (`TechtreeWeb.PublicationRate`), so an over-limit body is never read.
  pipeline :publishing do
    plug :accepts, ["json"]
    plug :put_public_api_headers
  end

  # The public profile page is temporarily withdrawn. Keep the owner-only
  # API and implementation intact for its later return.
  scope "/api/v1", TechtreeWeb do
    pipe_through :api
    get "/profile", SharedProfileController, :read
    patch "/profile", SharedProfileController, :update
    post "/profile/sync", SharedProfileController, :sync
  end

  scope "/", TechtreeWeb do
    pipe_through [:readable, :browser, :home_markdown]

    live "/", HomeLive
  end

  scope "/", TechtreeWeb do
    pipe_through [:readable, :browser]

    get "/about", PagesController, :about
    get "/contact", PagesController, :contact
    get "/privacy", PagesController, :privacy
    get "/skill.md", SkillController, :show
  end

  scope "/", TechtreeWeb do
    pipe_through [:html_only, :browser]

    get "/blog", BlogController, :index
    get "/blog/:slug", BlogController, :show
    live "/docs", DocsLive
    live "/changelog", ChangelogLive
    live "/proofs", ProofsLive
    live "/verify", ProofsLive
    live "/repo2rlenv", Repo2RLEnvLive
    live "/results", RunsLive.Index
    live "/results/:bundle_digest", RunsLive.Show
    live "/examples/tdd", TddShowcaseLive

    # The addresses release documents already point at, unchanged.
    live "/start", StartLive
    live "/climbs/:slug", ClimbsLive.Show
  end

  scope "/", TechtreeWeb do
    pipe_through :api

    get "/healthz", HealthController, :show
    get "/openapi.json", OpenAPIController, :show
  end

  scope "/", TechtreeWeb do
    get "/sitemap.xml", SitemapController, :index
    get "/llms.txt", AgentGuideController, :show
  end

  scope "/api/v1", TechtreeWeb do
    pipe_through :api

    get "/bootstrap", BootstrapController, :show
    get "/catalog", CatalogController, :index
    get "/climbs/:slug", ClimbController, :show
    get "/objects/:digest", ObjectController, :show
    get "/publications", PublicationController, :index
    get "/publications/:bundle_digest", PublicationController, :show
    get "/publications/:bundle_digest/bundle", PublicationController, :bundle
    get "/publication-keys/:key_id", PublicationKeyController, :show
  end

  # The one public write address, on its own so that what stands in front of
  # it is visible here rather than buried in a pipeline everything shares. The
  # profile routes above accept bodies only from the signed-in owner.
  scope "/api/v1", TechtreeWeb do
    pipe_through :publishing

    post "/publications", PublicationController, :create
  end

  defp put_public_api_headers(conn, _opts), do: TechtreeWeb.ExactResponse.put_api_headers(conn)

  defp answer_home_markdown(conn, _opts) do
    case get_format(conn) do
      "md" -> TechtreeWeb.MD.answer(conn, :home)
      "html" -> conn
    end
  end

  defp put_theme(conn, _opts) do
    assign(conn, :theme, saved_theme(conn.req_cookies[@theme_cookie]))
  end

  defp saved_theme(value) when value in ["light", "dark"], do: value
  defp saved_theme(_value), do: "light"
end
