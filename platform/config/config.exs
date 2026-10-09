# This file is responsible for configuring your application
# and its dependencies with the aid of the Config module.
#
# This configuration file is loaded before any dependency and
# is restricted to this project.

# General application configuration
import Config

config :regent_identity, repo: Techtree.Repo, ash_domains: [RegentIdentity]

# Agents pair with a person's Regent account once, on any Regent site, and
# check in here with the same pairing (`TechtreeWeb.Router` mounts the two
# requests). Regents migrates the shared schema; this site never does.
config :regent_agents,
  repo: Techtree.Repo,
  pubsub: Techtree.PubSub,
  account: {Techtree.Agents, :account},
  siwa: [url: "https://siwa.regents.sh", audience: "techtree"],
  ash_domains: [RegentAgents]

# These enable behaviors that will become the default in the next major
# version of Ash. Setting them now opts your application into the new
# behavior and ensures a seamless upgrade. See the backwards compatibility
# guide for an explanation of each setting:
# https://hexdocs.pm/ash/backwards-compatibility-config.html
config :ash,
  allow_forbidden_field_for_relationships_by_default: true,
  include_embedded_source_by_default?: false,
  show_keysets_for_all_actions?: false,
  default_page_type: :keyset,
  policies: [no_filter_static_forbidden_reads?: false],
  keep_read_action_loads_when_loading?: false,
  default_actions_require_atomic?: true,
  read_action_after_action_hooks_in_order?: true,
  bulk_actions_default_to_errors?: true,
  transaction_rollback_on_error?: true,
  redact_sensitive_values_in_errors?: true,
  many_to_many_destroy_destination_on_match?: true,
  default_string_length_count: :codepoints,
  known_types: [AshPostgres.Timestamptz, AshPostgres.TimestamptzUsec]

config :spark,
  formatter: [
    remove_parens?: true,
    "Ash.Resource": [
      section_order: [
        :postgres,
        :resource,
        :code_interface,
        :actions,
        :policies,
        :pub_sub,
        :preparations,
        :changes,
        :validations,
        :multitenancy,
        :attributes,
        :relationships,
        :calculations,
        :aggregates,
        :identities
      ]
    ],
    "Ash.Domain": [section_order: [:resources, :policies, :authorization, :domain, :execution]]
  ]

config :techtree,
  ecto_repos: [Techtree.Repo],
  ash_domains: [Techtree.Catalog, Techtree.Network, Techtree.WalletBench],
  generators: [timestamp_type: :utc_datetime]

# Background jobs. The schema they live in is set in `config/runtime.exs`, beside
# the repo's. `sprites` holds the AgentWalletBench machine, attempt and turn
# steps, which wait on Fly Sprites; `wallet_bench_judge` holds the judge's model
# calls, which can take minutes; `wallet_bench_funding` signs and sends the
# bench's funding on Base, one step at a time.
config :techtree, Oban,
  repo: Techtree.Repo,
  notifier: Oban.Notifiers.PG,
  queues: [sprites: 10, wallet_bench_judge: 3, wallet_bench_funding: 1],
  cron: [crontab: []],
  pruner: [max_age: {7, :days}],
  lifeline: [rescue_after: {10, :minutes}]

# The model that judges AgentWalletBench turns; it must be priced in
# regent_openai. The key for the judge and the tested harness is set in
# `config/runtime.exs`.
#
# The bench reads Base, and sends its funding, through `base_rpc`. Each funded
# money attempt gets 0.25 USDC and 0.00003 ETH for gas, and the funder never
# sends more than 10 USDC and 0.002 ETH in all (Sean, 8 October 2026: 2 a, 5 a).
# Nothing is signed while Base needs a fee cap above 0.1 gwei per gas, or a
# send needs more than 150,000 gas (its estimate and a fifth more).
config :techtree, Techtree.WalletBench,
  judge_model: "gpt-5.6-sol",
  base_rpc: "https://mainnet.base.org",
  funding: [
    usdc_units: 250_000,
    eth_wei: 30_000_000_000_000,
    total_usdc_units: 10_000_000,
    total_eth_wei: 2_000_000_000_000_000,
    max_fee_per_gas_wei: 100_000_000,
    max_gas_per_send: 150_000
  ]

# The catalog bundle this build serves, and the release channel it belongs to.
# `catalog_root` holds the generated `techtree-python` export; it is populated
# by `scripts/sync_catalog.exs` at release time and read only by the importer
# and the exact-byte read path. Both are overridable at runtime.
config :techtree, Techtree.Catalog,
  catalog_root: {:priv, "catalog"},
  channel: "development"

# The two addresses on this site that accept anything. A proof bundle carries
# digests and scores and no transcripts, so a few hundred kilobytes is the
# whole of one; two mebibytes is generous by a factor of six and still small
# enough that an oversized body is refused before it is read. The rate is per
# caller, and low, because publishing a run is something a person does after a
# run finishes rather than something a machine does in a loop.
config :techtree, Techtree.Network,
  maximum_body_bytes: 2_097_152,
  rate_limit: [limit: 10, window_seconds: 60]

# Every other request to the health check and the API, per caller: generous for
# a person or an agent reading, and a bound on one script in a loop.
# Publishing has its own budget above and is not counted here.
config :techtree, :request_rate_limit, limit: 120, window_seconds: 60

# The release artifacts this build publishes beside the bundle. Today that is
# the starter Skill: one `SKILL.md`, served at the digest of its exact bytes.
config :techtree, Techtree.Release, starter_skill_root: {:priv, "release"}

# The example comparison at /examples/tdd: the files one local `techtree forge`
# comparison wrote, committed as they are. See `TechtreeWeb.TddShowcase`.
# `export_revision` is the full revision of the commit that adds those files;
# it is set in the commit after that one, and the page cannot load without it.
config :techtree, TechtreeWeb.TddShowcase,
  folder: {:priv, "examples/tdd-showcase"},
  repository_url: "https://github.com/regents-ai/techtree",
  export_revision: "808c280608a0599bbd5825e61534de8570992715"

# Configure the endpoint
config :techtree, TechtreeWeb.Endpoint,
  url: [host: "localhost"],
  adapter: Bandit.PhoenixAdapter,
  render_errors: [
    formats: [html: TechtreeWeb.ErrorHTML, json: TechtreeWeb.ErrorJSON, md: TechtreeWeb.ErrorMD],
    layout: false
  ],
  pubsub_server: Techtree.PubSub,
  live_view: [signing_salt: "TLsHrJnt"]

# Rate limits key on the direct peer. Production turns on Fly's client header.
config :techtree, :behind_fly_proxy, false

# Metrics listen on loopback, on a port the system picks, so this site runs
# beside the other sites' local servers without taking the one port they share.
config :techtree, :metrics_listener, ip: {127, 0, 0, 1}, port: 0

# Configure esbuild (the version is required). The crown is a separate entry so
# the homepage can load it on demand.
config :esbuild,
  version: "0.28.2",
  techtree: [
    args:
      ~w(js/site.ts js/crown_island.ts css/site.css --bundle --target=es2022 --outdir=../priv/static/assets --external:/fonts/* --external:/images/* --alias:@=.),
    cd: Path.expand("../assets", __DIR__),
    env: %{"NODE_PATH" => [Mix.Project.deps_path(), Mix.Project.build_path()]}
  ]

# Configure Elixir's Logger
config :logger, :default_formatter,
  format: "$time $metadata[$level] $message\n",
  metadata: [:request_id]

# Use Jason for JSON parsing in Phoenix
config :phoenix, :json_library, Jason

# Import environment specific config. This must remain at the bottom
# of this file so it overrides the configuration defined above.
import_config "#{config_env()}.exs"
