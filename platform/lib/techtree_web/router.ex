defmodule TechtreeWeb.Router do
  @moduledoc """
  Public catalog and signed publication routes, plus the shared account and the
  person's own profile. Privy account authority never grants publication-key authority.
  """

  use TechtreeWeb, :router

  alias TechtreeWeb.Plugs.AgentWallet

  @theme_cookie "techtree_theme"

  # Pages are HTML here, and every public page also answers
  # `Accept: text/markdown`: the database-free ones from
  # `TechtreeWeb.PublicDocuments`, before the router, and the rest in
  # `:public_page` (`TechtreeWeb.Plugs.PageMarkdown`). `/skill.md` and
  # `/agents.md` are Markdown whichever is asked for.
  pipeline :html_only do
    plug :accepts, ["html"]
  end

  pipeline :readable do
    plug :accepts, ["html", "md"]
  end

  pipeline :public_page do
    plug :accepts, ["html", "md"]
    plug TechtreeWeb.Plugs.PageMarkdown
  end

  pipeline :browser do
    plug :fetch_session
    plug :fetch_cookies
    plug :fetch_live_flash
    plug :put_theme
    plug :put_root_layout, html: {TechtreeWeb.Layouts, :root}
    plug :protect_from_forgery
  end

  # Canonical authentication on every page, whose account menu signs in and out.
  # sobelow_skip ["Config.CSP"]
  pipeline :account_browser do
    plug :enforce_session_authority

    plug :put_secure_browser_headers, %{
      "content-security-policy" => TechtreeWeb.ContentSecurityPolicy.sign_in()
    }
  end

  # The public pages read the session the same way, but draw signed out when the
  # database connection is lost rather than failing whole.
  # sobelow_skip ["Config.CSP"]
  pipeline :visitor_browser do
    plug :enforce_visitor_session_authority

    plug :put_secure_browser_headers, %{
      "content-security-policy" => TechtreeWeb.ContentSecurityPolicy.sign_in()
    }
  end

  # The account pages and sign-in answers are never kept by the browser. Other
  # pages keep Phoenix's revalidated private caching, so back and forward work.
  pipeline :account_only do
    plug :no_store
  end

  scope "/", TechtreeWeb do
    pipe_through [:browser, :account_browser, :account_only]
    get "/auth/csrf", PrivySessionController, :csrf
    post "/auth/privy/failure", PrivySessionController, :failure
    post "/visit-log", VisitLogController, :create, log: false
    post "/auth/privy/session", PrivySessionController, :create
    get "/auth/session", PrivySessionController, :show
    delete "/auth/privy/session", PrivySessionController, :delete
  end

  scope "/", TechtreeWeb do
    pipe_through [:html_only, :browser, :account_browser, :account_only]

    live_session :account,
      session: {TechtreeWeb.Live.Session, :render_context, []},
      on_mount: [{TechtreeWeb.Live.Session, :load_human}] do
      live "/account", AccountShellLive, :account
      live "/account/agents", AccountShellLive, :account_agents
      live "/account/points", AccountShellLive, :points
      live "/account/wallets", AccountShellLive, :wallets
      live "/account/connections", AccountShellLive, :connections
      live "/watchdog", WatchdogLive, :index
    end
  end

  # The team's own pages: the site's admins only. Anyone else gets the
  # not-found page, signed in or not (TechtreeWeb.TeamGate).
  pipeline :team do
    plug TechtreeWeb.TeamGate
  end

  scope "/admin", TechtreeWeb do
    pipe_through [:html_only, :browser, :account_browser, :account_only, :team]

    live_session :team,
      session: {TechtreeWeb.Live.Session, :render_context, []},
      on_mount: [{TechtreeWeb.Live.Session, :load_human}, TechtreeWeb.TeamGate] do
      live "/messages", TeamMessagesLive, :index
    end
  end

  pipeline :api do
    plug :accepts, ["json"]
    plug :put_public_api_headers
  end

  # The Claude connector's sign-in (Techtree.OAuth), answered only while its
  # switch is on. API credentials never use cookies; consent uses the verified
  # browser and CSRF pipeline. The resource's metadata also answers under its
  # /mcp path, where RFC 9728 places it.
  scope "/", TechtreeWeb do
    pipe_through :api
    get "/.well-known/oauth-protected-resource", OAuthController, :resource_metadata
    get "/.well-known/oauth-protected-resource/mcp", OAuthController, :resource_metadata
    get "/.well-known/oauth-authorization-server", OAuthController, :server_metadata
    post "/oauth/register", OAuthController, :register, log: false
    post "/oauth/token", OAuthController, :token, log: false
    post "/oauth/revoke", OAuthController, :revoke, log: false
  end

  scope "/oauth", TechtreeWeb do
    pipe_through [:html_only, :browser, :account_browser, :account_only]
    get "/authorize", OAuthController, :authorize, log: false
    post "/authorize", OAuthController, :approve, log: false
    get "/connections", OAuthController, :connections, log: false
    post "/connections/revoke", OAuthController, :revoke_connection, log: false
  end

  # The hosted MCP server: AshAi runs the identity tools every Regent site gives
  # a connected app (`Techtree.Agents`) and the message an agent leaves the
  # team (`Techtree.Messages`), each as its Ash action with its policies.
  # McpAgent admits the request first: POST /mcp alone, JSON, one call,
  # no query string and no page from another site; then an agent signing with its
  # wallet or an app connected with a Bearer token from the sign-in above, never
  # neither. A connected app whose identity is paired calls as that agent. So
  # AshAi's own origin check takes whatever McpAgent let through. A tool's input
  # is checked as its action takes it (`TechtreeWeb.ToolErrors.check_input/3`).
  # No session, cookie or CSRF token is read. Each account has its own budget
  # here; the endpoint counts each address first. Nothing is kept between
  # requests. Tool calls carry pairing codes, so nothing is logged. There is no
  # `:accepts`: the endpoint already answers /mcp in JSON, so a GET for an event
  # stream hears McpAgent's 405, not a 406.
  pipeline :mcp do
    plug TechtreeWeb.Plugs.McpAgent
  end

  scope "/" do
    pipe_through :mcp

    forward "/mcp",
            AshAi.Mcp.Router,
            [
              otp_app: :techtree,
              tools:
                Enum.map(RegentMCPAgents.Tools.names(), &String.to_atom/1) ++ [:messages_leave],
              mcp_name: "techtree",
              instructions:
                "Techtree, where agents improve Skills and publish the results. " <>
                  "Every call carries the token of an app a person connected to their account here. " <>
                  "A connected app keeps one Regents identity: call register_identity, then get_identity. " <>
                  "If it is not paired, call pair_identity with the one-use code your person gives you, " <>
                  "your name and your harness, and call check_in so your person sees you are active. " <>
                  "An agent signing with its own wallet, or a paired app, leaves a private message " <>
                  "for Techtree's team with messages_leave. " <>
                  "Climbs, Results and publishing are on the API, signed by an agent's own wallet. " <>
                  "Never ask for a password, a private key or a wallet signature.",
              list_ttl_ms: 0,
              read_ttl_ms: 0,
              cache_scope: "private",
              allowed_origins: &is_binary/1,
              tool_argument_transformer: &TechtreeWeb.ToolErrors.check_input/3
            ],
            log: false
  end

  # A signed agent acts here as the person it is paired with, or not at all.
  pipeline :paired_agent do
    plug TechtreeWeb.Plugs.AgentWallet
    plug :acting_as_person
  end

  # A signed agent acts here as itself, paired or not.
  pipeline :signed_agent do
    plug TechtreeWeb.Plugs.AgentWallet
  end

  # The motion lab: public unless the showcase is off (TechtreeWeb.Showcase).
  pipeline :motion_lab do
    plug TechtreeWeb.Showcase, :motion_lab
  end

  # The person's shared profile, for the person signed in on this site or the
  # person a paired agent acts for (`TechtreeWeb.Plugs.ProfileOwner`). The
  # profile API answers its own methods and refusals (`RegentIdentity.HTTP`).
  pipeline :profile_owner do
    plug TechtreeWeb.Plugs.ProfileOwner
  end

  scope "/api/v1" do
    pipe_through [:api, :profile_owner]

    forward "/profile", RegentIdentity.HTTP
  end

  scope "/", TechtreeWeb do
    pipe_through [:readable, :browser]

    get "/skill.md", PublicPagesController, :skill_guide
  end

  # Retired addresses, each sent on for good to the page that took its place.
  scope "/", TechtreeWeb do
    get "/start", RedirectController, :show, assigns: %{to: "/docs/run-locally"}
    get "/verify", RedirectController, :show, assigns: %{to: "/docs/verify"}
    get "/docs/method", RedirectController, :show, assigns: %{to: "/docs/verify"}
    get "/repo2rlenv", RedirectController, :show, assigns: %{to: "/services/environments"}
    get "/train", RedirectController, :show, assigns: %{to: "/services/models"}
    get "/services/verify", RedirectController, :show, assigns: %{to: "/services/evals"}

    get "/services/verify/sample-report", RedirectController, :show,
      assigns: %{to: "/services/evals"}

    get "/services/cyber-assist", RedirectController, :show, assigns: %{to: "/services/security"}

    get "/services/cyber-assist/sample-report", RedirectController, :show,
      assigns: %{to: "/services/security/sample-report"}

    get "/services/watchdog", RedirectController, :show, assigns: %{to: "/services/security"}
  end

  scope "/", TechtreeWeb do
    pipe_through [:public_page, :browser, :visitor_browser]

    # The page's first render hands its visit to the connected page (TechtreeWeb.VisitLog).
    live_session :public, session: {TechtreeWeb.Live.Session, :render_context, []} do
      live "/", HomeLive
      get "/about", PublicPagesController, :show
      get "/privacy", PublicPagesController, :show
      get "/terms", PublicPagesController, :show
      get "/agents", PublicPagesController, :show
      get "/agents/:agent", PublicPagesController, :show
      get "/blog", BlogController, :index
      get "/blog/:slug", BlogController, :show
      live "/docs", DocsLive
      live "/docs/:slug", DocsLive
      live "/changelog", ChangelogLive
      live "/services/skills", ServiceLive, :skills
      live "/services/evals", ServiceLive, :evals
      live "/services/environments", ServiceLive, :environments
      live "/services/models", ServiceLive, :models
      live "/services/security", ServiceLive, :security
      get "/services/security/sample-report", PublicPagesController, :show
      live "/formal", FormalLive
      live "/results", RunsLive.Index
      live "/results/:bundle_digest", RunsLive.Show
      live "/examples/tdd", TddShowcaseLive
      live "/wallet-bench", WalletBenchLive.Index
      live "/wallet-bench/:id", WalletBenchLive.Show
      get "/wallet-bench/:id/evidence/:turn/:file", WalletBenchEvidenceController, :show
      get "/wallet-bench/:id/results.zip", WalletBenchEvidenceController, :results
      live "/train/:slug", TrainLive.Show

      # The address release documents already point at, unchanged.
      live "/climbs/:slug", ClimbsLive.Show
    end
  end

  scope "/", TechtreeWeb do
    pipe_through [:motion_lab, :html_only, :browser, :visitor_browser]

    live_session :motion_lab,
      session: {TechtreeWeb.Live.Session, :render_context, []},
      on_mount: [{TechtreeWeb.Showcase, :motion_lab}] do
      live "/animations", AnimationsLive, :index
    end
  end

  scope "/", TechtreeWeb do
    pipe_through :api

    get "/openapi.json", PublicPagesController, :openapi
  end

  scope "/", TechtreeWeb do
    pipe_through :api

    get "/wallet-bench.json", WalletBenchController, :scores
    get "/wallet-bench/:id/results.json", WalletBenchEvidenceController, :summary
    get "/train.json", TrainController, :index
  end

  scope "/", TechtreeWeb do
    get "/healthz", HealthController, :show
    get "/sitemap.xml", SitemapController, :index
    get "/results/:bundle_digest/share.png", ResultShareCardController, :show
    get "/robots.txt", PublicPagesController, :robots
    get "/agents.md", AgentsController, :show
    get "/agents/:agent/skill.md", PublicPagesController, :agent_skill_guide
    get "/wallet-bench.md", WalletBenchController, :markdown
    get "/train/:slug/report.json", TrainController, :report
    get "/train/:slug/traces.jsonl", TrainController, :traces
    get "/llms.txt", PublicPagesController, :llms
    get "/capabilities.json", PublicPagesController, :capabilities
    get "/.well-known/security.txt", PublicPagesController, :security
    get "/.well-known/api-catalog", PublicPagesController, :api_catalog
    get "/.well-known/agent-skills/*path", PublicPagesController, :agent_skill
  end

  scope "/api/v1", TechtreeWeb do
    pipe_through :api

    get "/health", HealthController, :status
    get "/docs", PublicPagesController, :document, assigns: %{document: "/docs"}
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
  # `TechtreeWeb.PublicationBody`). The profile above takes a change only for its
  # owner, from their session here or an agent they paired.
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

  # A paired agent's read of its person's Points, at the same path on every site.
  scope "/api/v1/account", TechtreeWeb do
    pipe_through [:api, :paired_agent]
    get "/points", AgentAccountController, :points
  end

  # A signed agent leaves Techtree's team a private message under a topic the
  # site names. It counts against the `/api` budget in `TechtreeWeb.Endpoint`
  # and against the message allowances (`Techtree.Messages.Message`).
  scope "/api/v1", TechtreeWeb do
    pipe_through [:api, :signed_agent]
    post "/messages/:topic", MessagesController, :leave
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

  defp acting_as_person(%{assigns: %{actor: %{pairing: :active}}} = conn, _opts), do: conn

  defp acting_as_person(%{assigns: %{actor: actor}} = conn, _opts) do
    code = AgentWallet.not_person_code(actor)
    {status, message, hint} = Map.fetch!(AgentWallet.not_person_refusals(), code)
    conn |> TechtreeWeb.ExactResponse.send_error(status, code, message, hint) |> halt()
  end

  defp put_theme(conn, _opts) do
    assign(conn, :theme, saved_theme(conn.req_cookies[@theme_cookie]))
  end

  # Until the visitor chooses, there is no theme and the device decides.
  defp saved_theme(value) when value in ["light", "dark"], do: value
  defp saved_theme(_value), do: nil

  defp no_store(conn, _opts), do: put_resp_header(conn, "cache-control", "private, no-store")

  defp enforce_session_authority(conn, _opts),
    do: TechtreeWeb.PrivySessionController.enforce_authority(conn, :account)

  defp enforce_visitor_session_authority(conn, _opts),
    do: TechtreeWeb.PrivySessionController.enforce_authority(conn, :public)
end
