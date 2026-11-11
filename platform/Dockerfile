# Build the deployed release, then throw the build away.
#
# The runtime image carries no compiler, no Mix, no Hex, and no source: it
# carries the assembled OTP release and the files that release publishes. What
# it publishes is fixed when this image is built, which is the point — the
# catalog bundle and the starter Skill are bytes inside the image, hashed again
# on every request, and a deploy is the only way they change.
#
# The versions below are the versions this repository is developed on, as
# ash-template's. The images stay on one Debian release: the release is linked
# against the builder's libraries and runs against the runner's.

# The image live when this one is built (platform/scripts/deploy_site.sh and
# scripts/release.sh name it), whose served files this release keeps while a
# deploy rolls over. Required.
ARG PREVIOUS_IMAGE

# gcc:16.2.0-trixie
FROM docker.io/library/gcc@sha256:07280eb2e744f1b7a2d8d4a3894c089ea07266c109758afc388a634bd098e4eb AS native
# hexpm/elixir:1.20.5-erlang-29.1.2-debian-trixie-20261027-slim
FROM docker.io/hexpm/elixir@sha256:bb266918bb26de22fb02ff19430f47e76331001601df0fc820806c21cd4164e0 AS elixir
# node:26.13.0-trixie-slim
FROM docker.io/library/node@sha256:e4db4c914bf8ad241bd24804fc25d272d89bad97e68cdc8a1414862790a02c39 AS node
# debian:trixie-20261027-slim
FROM docker.io/library/debian@sha256:f6b08b09a05725f9431502d3b5714f5c4576e82c1a84fa1debe0c24a7e0c3ec4 AS slim

FROM ${PREVIOUS_IMAGE} AS previous

# The gcc image brings the compiler for the native compilation picosat_elixir
# does, and git for Hex's git-sourced dependencies. Node and npm, copied from the
# node image, fetch the browser packages the site's bundles are built from. None
# of them survives into the runtime image.
FROM native AS builder

# The elixir image sets this and the gcc image does not.
ENV LANG=C.UTF-8

COPY --from=elixir /usr/local /usr/local
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm

WORKDIR /app

# Hex and rebar3 at fixed versions; rebar3 is the build Mix itself would pick
# for this Elixir and OTP, checked against its published SHA-512.
RUN mix local.hex 2.6.0 --force && \
  mix local.rebar rebar3 https://builds.hex.pm/installs/1.18.4/rebar3-3.28.0-otp-29 \
    --sha512 b51946058fbe4aa823185bfe27204be59be439982ac3a3e1dbd9f8260b9af046fcfdfbd9066283c3fbba5a2a45dc3570550c12a9a548daf223b80cac222a6d0f \
    --force

ENV MIX_ENV="prod"

# Stable npm dependencies precede Mix dependencies and application files.
COPY assets/package.json assets/package-lock.json assets/
# The browser dependency the hero canvas is drawn with, at the exact versions
# the lockfile pins. It is bundled into the site's own JavaScript below, so the
# served page still fetches nothing from anywhere but this site. Install scripts
# are off: they exist to fetch a native renderer for running this library
# outside a browser, which nothing here does. The TypeScript checker is a
# development tool for the gate, so it is left out.
RUN npm --prefix assets ci --omit=dev --ignore-scripts

# Dependencies first, and only the production ones, so that editing application
# code does not re-fetch or re-compile them. The shared Regent libraries are
# fetched from GitHub at the commits mix.lock pins.
COPY mix.exs mix.lock ./
RUN mix deps.get --only $MIX_ENV --check-locked

RUN mkdir config
COPY config/config.exs config/${MIX_ENV}.exs config/
RUN mix deps.compile

COPY priv priv
COPY lib lib
COPY blog_content /blog
COPY skills_content /skills
COPY assets assets

# Bundles and minifies the two asset files, then writes the digested copies and
# the cache manifest the endpoint serves them from.
RUN mix assets.deploy

RUN mix compile

# Runtime configuration is read when the release boots, not now.
COPY config/runtime.exs config/

COPY rel rel
RUN mix release

# A page the previous release served still asks for the files it was built with
# while the deploy rolls over, so they are kept beside this release's own: one
# release back, only what its manifest lists, never replacing a file of this one.
COPY --from=previous /app/lib /previous/lib
RUN mix techtree.keep_previous_assets /previous/lib _build/${MIX_ENV}/rel/techtree/lib

FROM slim

# Outbound TLS needs no CA bundle from the image: the release trusts castore's
# list (`Techtree.Application`). OTP 29 opens libsctp when it starts and prints
# a warning on every boot and `bin/techtree rpc` without it.
RUN apt-get update -y \
  && apt-get install -y --no-install-recommends libstdc++6 openssl libncurses6 locales libsctp1 \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

# The catalog is UTF-8 and is served as the exact bytes it was generated as.
RUN sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen && locale-gen
ENV LANG=en_US.UTF-8 \
    LANGUAGE=en_US:en \
    LC_ALL=en_US.UTF-8

WORKDIR /app
RUN chown nobody /app

ENV MIX_ENV="prod"

# The commit this image is built from, which /capabilities.json names.
# platform/scripts/deploy_site.sh and scripts/release.sh pass it; a build
# without it stops here.
ARG SOURCE_COMMIT
RUN test -n "$SOURCE_COMMIT"
ENV SOURCE_COMMIT=$SOURCE_COMMIT

COPY --from=builder --chown=nobody:root /app/_build/${MIX_ENV}/rel/techtree ./

USER nobody

# `bin/server` is the only entry point that sets `PHX_SERVER`, so `bin/migrate`
# and any `bin/techtree eval` run beside it do their work without a second
# process trying to bind the port.
CMD ["/app/bin/server"]
