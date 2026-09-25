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
  hostname: System.get_env("PGHOST", "localhost"),
  database: "techtree_test#{System.get_env("MIX_TEST_PARTITION")}",
  pool: Ecto.Adapters.SQL.Sandbox,
  # Keep parallel worktrees within the local PostgreSQL connection budget.
  pool_size: 8

# We don't run a server during test. If one is required,
# you can enable the server option below.
config :techtree, TechtreeWeb.Endpoint,
  url: [host: "127.0.0.1", port: browser_port],
  http: [ip: {127, 0, 0, 1}, port: browser_port],
  check_origin: ["http://127.0.0.1:#{browser_port}"],
  secret_key_base: "fJEVwbcHenhXO0I0VkIPCVbw+UngMhEYquu/I6Vvo87vhMrsp4BT5B6GM8Nkr+q7",
  server: false

# The example comparison reads test data made with the CLI's scripted stand-ins,
# and links its export at a stand-in revision.
config :techtree, TechtreeWeb.TddShowcase,
  folder: Path.expand("../test/support/fixtures/tdd-showcase", __DIR__),
  export_revision: "1234567890abcdef1234567890abcdef12345678"

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
