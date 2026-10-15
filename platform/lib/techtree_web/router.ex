defmodule TechtreeWeb.Router do
  @moduledoc """
  Public catalog and signed publication routes, plus the shared account and
  owner-only profile. Privy account authority never grants publication-key authority.
  """

  use TechtreeWeb, :router

  @theme_cookie "techtree_theme"

  # Pages are HTML here. The home page, About, Contact, Privacy, Terms and the
  # Changelog also answer `Accept: text/markdown`, from
  # `TechtreeWeb.PublicDocuments`, before the router. `/skill.md` and
  # `/agents.md` are Markdown whichever is asked for.
  pipeline :html_only do
    plug :accepts, ["html"]
  end

  pipeline :readable do
    plug :accepts, ["html", "md"]
  end

  pipeline :browser do
    plug :fetch_session
    plug :fetch_cookies
    plug :fetch_live_flash
    plug :put_theme
    plug :put_root_layout, html: {TechtreeWeb.Layouts, :root}
    plug :protect_from_forgery
  end

  # Canonical authentication only on account and sign-in routes.
  # sobelow_skip ["Config.CSP"]
  pipeline :account_browser do
    plug :enforce_session_authority

    plug :put_secure_browser_headers, %{
      "content-security-policy" => TechtreeWeb.ContentSecurityPolicy.sign_in(),
      "cache-control" => "private, no-store"
    }
  end

  scope "/", TechtreeWeb do
    pipe_through [:browser, :account_browser]
    get "/auth/csrf", PrivySessionController, :csrf
    post "/auth/privy/failure", PrivySessionController, :failure
    post "/auth/privy/session", PrivySessionController, :create
    get "/auth/session", PrivySessionController, :show
    delete "/auth/privy/session", PrivySessionController, :delete
  end

  scope "/", TechtreeWeb do
    pipe_through [:html_only, :browser, :account_browser]

    live_session :account,
      session: {TechtreeWeb.Live.Session, :render_context, []},
      on_mount: [{TechtreeWeb.Live.Session, :load_human}] do
      live "/account", AccountShellLive, :account
      live "/account/points", AccountShellLive, :points
      live "/account/credits", AccountShellLive, :credits
      live "/account/wallets", AccountShellLive, :wallets
      live "/account/connections", AccountShellLive, :connections
    end
  end

  pipeline :api do
    plug :accepts, ["json"]
    plug :put_public_api_headers
  end

  pipeline :paired_agent do
    plug TechtreeWeb.Plugs.PairedAgent
  end

  # The motion lab: public unless the showcase is off (TechtreeWeb.Showcase).
  pipeline :motion_lab do
    plug TechtreeWeb.Showcase, :motion_lab
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
    pipe_through [:readable, :browser]

    get "/skill.md", SkillController, :show
  end

  scope "/", TechtreeWeb do
    pipe_through [:html_only, :browser]

    live "/", HomeLive
    get "/about", PublicPagesController, :show
    get "/contact", PublicPagesController, :show
    get "/privacy", PublicPagesController, :show
    get "/terms", PublicPagesController, :show
    get "/blog", BlogController, :index
    get "/blog/:slug", BlogController, :show
    live "/docs", DocsLive
    live "/changelog", ChangelogLive
    live "/verify", ProofsLive
    live "/repo2rlenv", Repo2RLEnvLive
    live "/results", RunsLive.Index
    live "/results/:bundle_digest", RunsLive.Show
    live "/examples/tdd", TddShowcaseLive
    live "/wallet-bench", WalletBenchLive.Index
    live "/wallet-bench/:id", WalletBenchLive.Show
    get "/wallet-bench/:id/evidence/:turn/:file", WalletBenchEvidenceController, :show

    # The addresses release documents already point at, unchanged.
    live "/start", StartLive
    live "/climbs/:slug", ClimbsLive.Show
  end

  scope "/", TechtreeWeb do
    pipe_through [:motion_lab, :html_only, :browser]

    live_session :motion_lab, on_mount: [{TechtreeWeb.Showcase, :motion_lab}] do
      live "/animations", AnimationsLive, :index
    end
  end

  scope "/", TechtreeWeb do
    pipe_through :api

    get "/healthz", HealthController, :show
    get "/openapi.json", PublicPagesController, :openapi
  end

  scope "/", TechtreeWeb do
    get "/sitemap.xml", SitemapController, :index
    get "/robots.txt", PublicPagesController, :robots
    get "/agents.md", AgentsController, :show
    get "/wallet-bench.md", WalletBenchController, :markdown
    get "/llms.txt", PublicPagesController, :llms
    get "/capabilities", PublicPagesController, :capabilities
    get "/.well-known/security.txt", PublicPagesController, :security
    get "/.well-known/api-catalog", PublicPagesController, :api_catalog
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
    get "/skills/:root_digest", PublishedSkillController, :show
  end

  # The one paired-agent write address. Its rate limit and exact-byte reader stand
  # in the endpoint, in front of the parser (`TechtreeWeb.PublicationRate`,
  # `TechtreeWeb.PublicationBody`). The profile routes above accept bodies only
  # from the signed-in owner.
  scope "/api/v1", TechtreeWeb do
    pipe_through [:api, :paired_agent]

    post "/publications", PublicationController, :create
  end

  # Model Climb proofs: a paired agent sends its person's signed proofs and
  # reads them back; each is private to that person. The proof's exact bytes
  # are read by `TechtreeWeb.PublicationBody` and counted by
  # `TechtreeWeb.PublicationRate`, like a publication.
  scope "/api/model-climb/v1", TechtreeWeb do
    pipe_through [:api, :paired_agent]
    post "/reports", ModelClimbReportController, :create
    get "/reports", ModelClimbReportController, :index
    get "/reports/:digest", ModelClimbReportController, :show
  end

  scope "/tools/account", TechtreeWeb do
    pipe_through [:api, :paired_agent]
    get "/balances", AgentAccountController, :balances
    post "/credits/history", AgentAccountController, :history
    get "/points", AgentAccountController, :points
  end

  # An agent pairs with its person's Regent account and checks in, signing each
  # request with its SIWA key. Both count against the `/api` budget in
  # `TechtreeWeb.Endpoint`, and a pairing's exact bytes are kept by
  # `TechtreeWeb.PublicationBody`.
  scope "/api" do
    pipe_through :api

    forward "/agents/v1", RegentAgents.HTTP
  end

  defp put_public_api_headers(conn, _opts), do: TechtreeWeb.ExactResponse.put_api_headers(conn)

  defp put_theme(conn, _opts) do
    assign(conn, :theme, saved_theme(conn.req_cookies[@theme_cookie]))
  end

  # Until the visitor chooses, there is no theme and the device decides.
  defp saved_theme(value) when value in ["light", "dark"], do: value
  defp saved_theme(_value), do: nil

  defp enforce_session_authority(conn, _opts),
    do: TechtreeWeb.PrivySessionController.enforce_authority(conn)
end
