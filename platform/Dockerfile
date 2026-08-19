# Build the deployed release, then throw the build away.
#
# The runtime image carries no compiler, no Mix, no Hex, and no source: it
# carries the assembled OTP release and the files that release publishes. What
# it publishes is fixed when this image is built, which is the point — the
# catalog bundle and the starter Skill are bytes inside the image, hashed again
# on every request, and a deploy is the only way they change.
#
# The versions below are the versions this repository is developed on. Keep the
# Debian date on the builder and the runner identical: the release is linked
# against the builder's libraries and runs against the runner's.

ARG ELIXIR_VERSION=1.19.5
ARG OTP_VERSION=28.2
ARG DEBIAN_VERSION=trixie-20260803

ARG BUILDER_IMAGE="hexpm/elixir:${ELIXIR_VERSION}-erlang-${OTP_VERSION}-debian-${DEBIAN_VERSION}-slim"
ARG RUNNER_IMAGE="debian:${DEBIAN_VERSION}-slim"

FROM ${BUILDER_IMAGE} AS builder

# git is needed by Hex for any git-sourced dependency; build-essential for the
# native compilation picosat_elixir does.
RUN apt-get update -y \
  && apt-get install -y --no-install-recommends build-essential git ca-certificates \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN mix local.hex --force && mix local.rebar --force

ENV MIX_ENV="prod"

# Dependencies first, and only the production ones, so that editing application
# code does not re-fetch or re-compile them.
COPY mix.exs mix.lock ./
RUN mix deps.get --only $MIX_ENV

RUN mkdir config
COPY config/config.exs config/${MIX_ENV}.exs config/
RUN mix deps.compile

COPY priv priv
COPY lib lib
COPY assets assets

# Bundles and minifies the two asset files, then writes the digested copies and
# the cache manifest the endpoint serves them from.
RUN mix assets.deploy

RUN mix compile

# Runtime configuration is read when the release boots, not now.
COPY config/runtime.exs config/

COPY rel rel
RUN mix release

FROM ${RUNNER_IMAGE}

RUN apt-get update -y \
  && apt-get install -y --no-install-recommends libstdc++6 openssl libncurses6 locales ca-certificates \
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

COPY --from=builder --chown=nobody:root /app/_build/${MIX_ENV}/rel/techtree ./

USER nobody

# `bin/server` is the only entry point that sets `PHX_SERVER`, so `bin/migrate`
# and any `bin/techtree eval` run beside it do their work without a second
# process trying to bind the port.
CMD ["/app/bin/server"]
