import Config
browser_port = String.to_integer(System.get_env("PORT", "4002"))
config :ash, policies: [show_policy_breakdowns?: true], disable_async?: true

# Configure your database
#
# The MIX_TEST_PARTITION environment variable can be used
# to provide built-in test partitioning in CI environment.
# Run `mix help test` for more information.
config :techtree, Techtree.Repo,
  username: System.get_env("PGUSER", "postgres"),
  password: System.get_env("PGPASSWORD", "postgres"),
  hostname: System.get_env("PGHOST", "127.0.0.1"),
  database: "techtree#{System.get_env("MIX_TEST_PARTITION")}_test",
  pool: Ecto.Adapters.SQL.Sandbox,
  # Keep parallel worktrees within the local PostgreSQL connection budget.
  pool_size: 8

# Tests never reach a chain or the shared sign-in service: every address they
# would call is a closed local port, so a read that isn't stubbed fails at once
# instead of reaching Base, Ethereum or siwa.regents.sh. Any request that still
# names an outside host raises where it starts (Techtree.OfflineHttp).
nowhere = "http://127.0.0.1:9"

config :req, default_options: [adapter: Techtree.OfflineHttp]

config :regent_credits,
  chains: %{
    base: %{chain_id: 8453, name: "Base", rpc_url: nowhere},
    ethereum: %{chain_id: 1, name: "Ethereum", rpc_url: nowhere}
  }

config :regent_agents, siwa: [url: nowhere, audience: "techtree"]
config :techtree, Techtree.WalletBench, base_rpc: nowhere
config :techtree, :chain_nodes, %{8453 => nowhere, 1 => nowhere}
config :techtree, :github_stars, api_url: nowhere, repository: "regents-ai/techtree"

# The browser test server (assets/test/browser) answers real page loads, which
# commit what they write, so it runs on an ordinary pool of three on its own
# database (MIX_TEST_PARTITION=browser) rather than the test sandbox.
# Its wallet tests' recorded files are kept in a folder on this machine
# (Techtree.EvidenceShelf) rather than the private bucket.
if System.get_env("TECHTREE_BROWSER_TEST") == "1" do
  config :techtree, Techtree.Repo, pool: DBConnection.ConnectionPool, pool_size: 3

  config :techtree, Techtree.WalletBench.Evidence,
    endpoint: nowhere,
    bucket: "evidence",
    region: "auto",
    access_key_id: "browser-tests",
    secret_access_key: "browser-tests",
    req_options: [plug: Techtree.EvidenceShelf]
end

# We don't run a server during test. If one is required,
# you can enable the server option below.
config :techtree, TechtreeWeb.Endpoint,
  url: [host: "127.0.0.1", port: browser_port],
  http: [ip: {127, 0, 0, 1}, port: browser_port],
  check_origin: ["http://127.0.0.1:#{browser_port}"],
  secret_key_base: "fJEVwbcHenhXO0I0VkIPCVbw+UngMhEYquu/I6Vvo87vhMrsp4BT5B6GM8Nkr+q7",
  # The browser tests (assets/test/browser) start this server themselves.
  server: System.get_env("TECHTREE_BROWSER_TEST") == "1"

# The example comparison reads test data made with the CLI's scripted stand-ins,
# and links its export at a stand-in revision.
config :techtree, TechtreeWeb.TddShowcase,
  folder: Path.expand("../test/support/fixtures/tdd-showcase", __DIR__),
  export_revision: "1234567890abcdef1234567890abcdef12345678"

# Every test request comes from one address, so the suite would spend the
# request budget within a minute.
config :techtree, :request_rate_limit, limit: 1_000_000, window_seconds: 60

# Publishing keeps its real budget, but over a window that doesn't turn over
# during a run, so a test that sends one request too many is refused even when
# a minute ticks over halfway through it. Techtree.RateLimitTest covers the
# turnover with its own clock.
config :techtree, Techtree.Network,
  rate_limit: [limit: 10, window_seconds: 1_000_000_000],
  agent_rate_limit: [limit: 10, window_seconds: 1_000_000_000]

config :techtree, Oban, testing: :manual

# Agents' signed requests reach a stub of the sign-in service, never the real
# one (`Req.Test.stub(RegentAgents.Broker, ...)`, `Techtree.NetworkFixture.sign_as/1`).
config :regent_agents, req_options: [plug: {Req.Test, RegentAgents.Broker}]

# Print only warnings and errors during test
config :logger, level: :warning

# Initialize plugs at runtime for faster test compilation
config :phoenix, :plug_init_mode, :runtime

# Enable helpful, but potentially expensive runtime checks
config :phoenix_live_view,
  enable_expensive_runtime_checks: true

# Sort query params output of verified routes for robust url comparisons
config :phoenix,
  sort_verified_routes_query_params: true
