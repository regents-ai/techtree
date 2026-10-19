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
ARG OTP_VERSION=28.3.1
ARG DEBIAN_VERSION=trixie-20260610
ARG TECHTREE_SOURCE_REVISION
# The image live when this one is built (scripts/deploy_site.sh names it), whose
# served files this release keeps while a deploy rolls over. Required.
ARG PREVIOUS_IMAGE

ARG BUILDER_IMAGE="hexpm/elixir:${ELIXIR_VERSION}-erlang-${OTP_VERSION}-debian-${DEBIAN_VERSION}-slim"
ARG RUNNER_IMAGE="debian:${DEBIAN_VERSION}-slim"

# Node and npm come from this digest-pinned image (as ash-template's), so the npm
# that installs the browser packages is the same npm 11 that writes the lockfile.
FROM docker.io/library/node@sha256:5aea649bacdc35e8e20571131c4f3547477dfe66e677d45c005af6dbd1edfaa7 AS node

FROM ${PREVIOUS_IMAGE} AS previous

FROM ${BUILDER_IMAGE} AS builder

ARG TECHTREE_SOURCE_REVISION
RUN case "$TECHTREE_SOURCE_REVISION" in \
      [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]) ;; \
      *) echo "TECHTREE_SOURCE_REVISION must be the clean 40-character git revision" >&2; exit 1 ;; \
    esac

# git is needed by Hex for any git-sourced dependency; build-essential for the
# native compilation picosat_elixir does. Node and npm, copied from the node
# image, fetch the browser packages the site's bundles are built from.
# None of them survives into the runtime image.
RUN apt-get update -y \
  && apt-get install -y --no-install-recommends build-essential git ca-certificates \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm

WORKDIR /app

RUN mix local.hex --force && mix local.rebar --force

ENV MIX_ENV="prod"

# Dependencies first, and only the production ones, so that editing application
# code does not re-fetch or re-compile them. The shared Regent libraries are
# fetched from GitHub at the commits mix.lock pins.
COPY mix.exs mix.lock ./
RUN mix deps.get --only $MIX_ENV

RUN mkdir config
COPY config/config.exs config/${MIX_ENV}.exs config/
RUN mix deps.compile

COPY priv priv
COPY lib lib
COPY blog_content /blog
COPY skills_content /skills
COPY assets assets

# The browser dependency the hero canvas is drawn with, at the exact versions
# the lockfile pins. It is bundled into the site's own JavaScript below, so the
# served page still fetches nothing from anywhere but this site. Install scripts
# are off: they exist to fetch a native renderer for running this library
# outside a browser, which nothing here does. The TypeScript checker is a
# development tool for the gate, so it is left out.
RUN npm --prefix assets ci --omit=dev --ignore-scripts

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

FROM ${RUNNER_IMAGE}

ARG TECHTREE_SOURCE_REVISION
ENV TECHTREE_SOURCE_REVISION=$TECHTREE_SOURCE_REVISION
LABEL org.opencontainers.image.revision=$TECHTREE_SOURCE_REVISION

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
