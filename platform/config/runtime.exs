import Config

# config/runtime.exs is executed for all environments, including
# during releases. It is executed after compilation and before the
# system starts, so it is typically used to load production configuration
# and secrets from environment variables or elsewhere. Do not define
# any compile-time configuration in here, as it won't be applied.
# The block below contains prod specific runtime configuration.

# ## Using releases
#
# If you use `mix release`, you need to explicitly enable the server
# by passing the PHX_SERVER=true when you start it:
#
#     PHX_SERVER=true bin/techtree start
#
# Alternatively, you can use `mix phx.gen.release` to generate a `bin/server`
# script that automatically sets the env var above.
# The channel this build serves, overridable at boot. It belongs here rather
# than beside the default in `config.exs`, because that file is evaluated when
# the project is compiled: an environment variable read there is read once, at
# build time, and a later value is silently ignored.
#
# The staged publication rehearsal is why it exists. The release candidate
# publishes the stable channel while development is the default, and rehearsing
# a release should not mean editing a committed default for the occasion.
if channel = System.get_env("TECHTREE_CATALOG_CHANNEL") do
  config :techtree, Techtree.Catalog,
    catalog_root: {:priv, "catalog"},
    channel: channel
end

# The public hostname, honoured wherever it is set rather than only in a
# release. A staged rehearsal serves the real log's addresses from a local
# port: the submission travels to an overridden endpoint, while the receipt it
# answers with has to name the log's real address, because the participant's
# CLI checks that against the origin its release pins and refuses anything
# else. Refusing is the pin doing its job, so the rehearsal has to satisfy it
# rather than route around it.
if config_env() != :prod do
  if host = System.get_env("PHX_HOST") do
    config :techtree, TechtreeWeb.Endpoint, url: [host: host, port: 443, scheme: "https"]
  end
end

if System.get_env("PHX_SERVER") do
  config :techtree, TechtreeWeb.Endpoint, server: true
end

config :techtree, TechtreeWeb.Endpoint,
  http: [port: String.to_integer(System.get_env("PORT", "4000"))]

# Catalog serving configuration. `TECHTREE_CATALOG_ROOT` points at a generated
# bundle outside the release; without it the bundle shipped in `priv/catalog`
# is used. `TECHTREE_BOOTSTRAP_CHANNEL` selects the release channel that is
# imported and served; unset, it stays on the compile-time default in
# `config/config.exs`, which is `development` — the channel whose staged
# release is the declared placeholder. An unset variable therefore publishes
# the placeholder, never the Gate-2 candidate. No model-provider credential is
# read here.
config :techtree,
       Techtree.Catalog,
       Enum.reject(
         [
           catalog_root: System.get_env("TECHTREE_CATALOG_ROOT"),
           channel: System.get_env("TECHTREE_BOOTSTRAP_CHANNEL")
         ],
         fn {_key, value} -> is_nil(value) end
       )

# The key this site countersigns publication receipts with. The private half is
# operational configuration and lives nowhere in this repository: it is the
# base64 of 32 bytes of Ed25519 private key, generated on a machine the operator
# trusts and set as a secret. Without it the publish address and the key address
# both answer 503, which `Techtree.Network.Key` explains; a production release
# refuses to boot rather than reach that state by omission.
config :techtree,
       Techtree.Network.Key,
       private_key: System.get_env("TECHTREE_NETWORK_SIGNING_KEY")

if config_env() == :prod do
  network_signing_key =
    System.get_env("TECHTREE_NETWORK_SIGNING_KEY") ||
      raise """
      environment variable TECHTREE_NETWORK_SIGNING_KEY is missing.
      It is the base64 of the 32 bytes of the Ed25519 private key this site
      countersigns publication receipts with. Generate one on a machine you
      trust and set it as a secret; it must never be written into this
      repository. The public half is served at /api/v1/network-key.
      """

  # The value itself is never printed, here or anywhere else. A misconfigured
  # key that only announced itself the first time somebody published a run
  # would be found by a participant rather than by the operator.
  if not match?({:ok, decoded} when byte_size(decoded) == 32, Base.decode64(network_signing_key)) do
    raise """
    environment variable TECHTREE_NETWORK_SIGNING_KEY is not usable.
    It must be the base64 of exactly 32 bytes of Ed25519 private key.
    """
  end

  database_url =
    System.get_env("DATABASE_URL") ||
      raise """
      environment variable DATABASE_URL is missing.
      For example: ecto://USER:PASS@HOST/DATABASE
      """

  maybe_ipv6 = if System.get_env("ECTO_IPV6") in ~w(true 1), do: [:inet6], else: []

  config :techtree, Techtree.Repo,
    # ssl: true,
    url: database_url,
    pool_size: String.to_integer(System.get_env("POOL_SIZE") || "10"),
    # For machines with several cores, consider starting multiple pools of `pool_size`
    # pool_count: 4,
    socket_options: maybe_ipv6

  # The secret key base is used to sign/encrypt cookies and other secrets.
  # A default value is used in config/dev.exs and config/test.exs but you
  # want to use a different value for prod and you most likely don't want
  # to check this value into version control, so we use an environment
  # variable instead.
  secret_key_base =
    System.get_env("SECRET_KEY_BASE") ||
      raise """
      environment variable SECRET_KEY_BASE is missing.
      You can generate one by calling: mix phx.gen.secret
      """

  # Every absolute URL this site prints — and the origin its live pages are
  # allowed to connect from — is built from this. A host guessed wrong is a
  # site that quietly publishes addresses nobody can fetch, so it is named
  # rather than defaulted.
  host =
    System.get_env("PHX_HOST") ||
      raise """
      environment variable PHX_HOST is missing.
      It is the public hostname this site is served on, for example: techtree.sh
      """

  config :techtree, :dns_cluster_query, System.get_env("DNS_CLUSTER_QUERY")

  config :techtree, TechtreeWeb.Endpoint,
    url: [host: host, port: 443, scheme: "https"],
    http: [
      # Enable IPv6 and bind on all interfaces.
      # Set it to  {0, 0, 0, 0, 0, 0, 0, 1} for local network only access.
      # See the documentation on https://hexdocs.pm/bandit/Bandit.html#t:options/0
      # for details about using IPv6 vs IPv4 and loopback vs public addresses.
      ip: {0, 0, 0, 0, 0, 0, 0, 0}
    ],
    secret_key_base: secret_key_base

  # ## SSL Support
  #
  # To get SSL working, you will need to add the `https` key
  # to your endpoint configuration:
  #
  #     config :techtree, TechtreeWeb.Endpoint,
  #       https: [
  #         ...,
  #         port: 443,
  #         cipher_suite: :strong,
  #         keyfile: System.get_env("SOME_APP_SSL_KEY_PATH"),
  #         certfile: System.get_env("SOME_APP_SSL_CERT_PATH")
  #       ]
  #
  # The `cipher_suite` is set to `:strong` to support only the
  # latest and more secure SSL ciphers. This means old browsers
  # and clients may not be supported. You can set it to
  # `:compatible` for wider support.
  #
  # `:keyfile` and `:certfile` expect an absolute path to the key
  # and cert in disk or a relative path inside priv, for example
  # "priv/ssl/server.key". For all supported SSL configuration
  # options, see https://hexdocs.pm/plug/Plug.SSL.html#configure/1
  #
  # We also recommend setting `force_ssl` in your config/prod.exs,
  # ensuring no data is ever sent via http, always redirecting to https:
  #
  #     config :techtree, TechtreeWeb.Endpoint,
  #       force_ssl: [hsts: true]
  #
  # Check `Plug.SSL` for all available options in `force_ssl`.
end
