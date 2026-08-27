# This file is responsible for configuring your application
# and its dependencies with the aid of the Config module.
#
# This configuration file is loaded before any dependency and
# is restricted to this project.

# General application configuration
import Config

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
  ash_domains: [Techtree.Catalog, Techtree.Network],
  generators: [timestamp_type: :utc_datetime]

# The catalog bundle this build serves, and the release channel it belongs to.
# `catalog_root` holds the generated `techtree-python` export; it is populated
# by `scripts/sync_catalog.exs` at release time and read only by the importer
# and the exact-byte read path. Both are overridable at runtime.
config :techtree, Techtree.Catalog,
  catalog_root: {:priv, "catalog"},
  channel: "development"

# The one address on this site that accepts anything. A proof bundle carries
# digests and scores and no transcripts, so a few hundred kilobytes is the
# whole of one; the cap is generous by an order of magnitude and still small
# enough that an oversized body is refused before it is read. The rate is per
# caller, and low, because publishing a run is something a person does after a
# run finishes rather than something a machine does in a loop.
config :techtree, Techtree.Network,
  maximum_body_bytes: 4_000_000,
  rate_limit: [limit: 10, window_seconds: 60]

# The release artifacts this build publishes beside the bundle. Today that is
# the starter Skill: one `SKILL.md`, served at the digest of its exact bytes.
config :techtree, Techtree.Release, starter_skill_root: {:priv, "release"}

# Configure the endpoint
config :techtree, TechtreeWeb.Endpoint,
  url: [host: "localhost"],
  adapter: Bandit.PhoenixAdapter,
  render_errors: [
    formats: [html: TechtreeWeb.ErrorHTML, json: TechtreeWeb.ErrorJSON],
    layout: false
  ],
  pubsub_server: Techtree.PubSub,
  live_view: [signing_salt: "TLsHrJnt"]

# Configure esbuild (the version is required). It builds both bundles: the
# stylesheet is plain CSS with no framework behind it, so it needs no second
# tool of its own.
config :esbuild,
  version: "0.25.4",
  techtree: [
    args:
      ~w(js/app.js css/app.css --bundle --target=es2022 --outdir=../priv/static/assets --external:/fonts/* --external:/images/* --alias:@=.),
    cd: Path.expand("../assets", __DIR__),
    env: %{"NODE_PATH" => [Path.expand("../deps", __DIR__), Mix.Project.build_path()]}
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
