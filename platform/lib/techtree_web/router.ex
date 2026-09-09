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

  pipeline :browser do
    plug :accepts, ["html"]
    plug :fetch_session
    plug :fetch_cookies
    plug :fetch_live_flash
    plug :put_theme
    plug :put_root_layout, html: {TechtreeWeb.Layouts, :root}
    plug :protect_from_forgery

    plug :put_secure_browser_headers, %{
      "content-security-policy" => @content_security_policy,
      "referrer-policy" => "no-referrer"
    }
  end

  pipeline :api do
    plug :accepts, ["json"]
    plug :put_public_api_headers
  end

  # The one pipeline in front of the one address that accepts a body.
  pipeline :publishing do
    plug :accepts, ["json"]
    plug :put_public_api_headers
    plug TechtreeWeb.PublicationRate
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
    pipe_through :browser

    live "/", HomeLive
    get "/blog", BlogController, :index
    get "/blog/:slug", BlogController, :show
    live "/docs", DocsLive
    live "/proofs", ProofsLive
    live "/verify", ProofsLive
    live "/repo2rlenv", Repo2RLEnvLive
    live "/results", RunsLive.Index
    live "/results/:bundle_digest", RunsLive.Show
    get "/skill.md", SkillController, :show

    # The addresses release documents already point at, unchanged.
    live "/start", StartLive
    live "/climbs/:slug", ClimbsLive.Show
  end

  scope "/", TechtreeWeb do
    pipe_through :api

    get "/healthz", HealthController, :show
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

  # The one address that accepts anything, on its own so that what stands in
  # front of it is visible here rather than buried in a pipeline everything
  # shares.
  scope "/api/v1", TechtreeWeb do
    pipe_through :publishing

    post "/publications", PublicationController, :create
  end

  # An API response is data, never a document: nothing in it may be sniffed into
  # a content type it did not declare, loaded as a page resource, framed, or
  # allowed to leak a referrer.
  defp put_public_api_headers(conn, _opts) do
    conn
    |> put_resp_header("x-content-type-options", "nosniff")
    |> put_resp_header("content-security-policy", "default-src 'none'; frame-ancestors 'none'")
    |> put_resp_header("x-frame-options", "DENY")
    |> put_resp_header("referrer-policy", "no-referrer")
  end

  defp put_theme(conn, _opts) do
    theme =
      case conn.request_path do
        "/crown/2" -> "light"
        "/crown/4" -> "dark"
        _path -> saved_theme(conn.req_cookies[@theme_cookie])
      end

    assign(conn, :theme, theme)
  end

  defp saved_theme(value) when value in ["light", "dark"], do: value
  defp saved_theme(_value), do: "light"

  # Previews of work heading for `/`, and nothing a release publishes.
  #
  # Founder ruling 2026-08-28: these are for him to look at while the front
  # page is being reworked, and they are not v0.1 routes. They live behind
  # `dev_routes` rather than in the scope above because the routing table IS
  # the published surface — `router_test.exs` pins it and the Gate-2 packet
  # asserts it, so a preview sitting in that table would be a coordinate
  # somebody had to have decided rather than a page somebody wanted to see.
  #
  # `dev_routes` is set only in `config/dev.exs`, so these compile away
  # entirely in test and in a release.
  if Application.compile_env(:techtree, :dev_routes) do
    scope "/", TechtreeWeb do
      pipe_through :browser

      live "/crown/1", HomeLive, :crown_1
      live "/crown/2", HomeLive, :crown_2
      live "/crown/3", HomeLive, :crown_3
      live "/crown/4", HomeLive, :crown_4
      live "/prism", PrismLive
    end
  end
end
