#!/usr/bin/env bash
set -euo pipefail

repository_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repository_root"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Refusing to deploy: the working tree is not clean." >&2
  exit 1
fi

source_revision="$(git rev-parse HEAD)"
upstream_revision="$(git rev-parse '@{u}')"

if [[ "$source_revision" != "$upstream_revision" ]]; then
  echo "Refusing to deploy: HEAD has not been pushed to its upstream branch." >&2
  exit 1
fi

# The live image, whose served files the new release keeps through the rollover,
# and one of those files, asked for again once the deploy is done.
if ! live_images="$(flyctl image show --app techtree-sh --json | jq -er 'map("\(.Registry)/\(.Repository)@\(.Digest)") | unique | .[]')"; then
  echo "Refusing to deploy: the live image can't be read, so its files can't be kept." >&2
  exit 1
fi

if [[ "$(wc -l <<<"$live_images" | tr -d ' ')" != 1 ]]; then
  echo "Refusing to deploy: the machines run different images, so there is no one release to keep files from:" >&2
  echo "$live_images" >&2
  exit 1
fi

previous_image="$live_images"

if [[ "$previous_image" != registry.fly.io/techtree-sh@sha256:* ]]; then
  echo "Refusing to deploy: the live image can't be read, so its files can't be kept." >&2
  exit 1
fi

# The page is read whole before it is searched, so a large page is never cut
# short by the search stopping early.
if ! live_page="$(curl -fsS https://techtree.sh/)"; then
  echo "Refusing to deploy: the live page can't be read, so no script can be checked afterwards." >&2
  exit 1
fi

if ! previous_script="$(grep -o -m 1 '/assets/js/site-[0-9a-f]*\.js' <<<"$live_page")"; then
  echo "Refusing to deploy: the live page names no script to check afterwards." >&2
  exit 1
fi

# The blog's posts and images and the Techtree skill live beside platform/ and
# are compiled in, so they are copied into this application-only build context.
rsync -a --delete ../blog/ blog_content/
rsync -a --delete ../skills/ skills_content/

# Every site shares one production database, and a release briefly doubles a
# site's connections, so releases from this machine take turns: the build and
# release run under one lock that every site's deploy takes, and wait for it.
lock=/tmp/regent-shared-db-release.lock
echo "==> Deploying ${source_revision:0:7} to techtree-sh (waits for any other release holding $lock)"
lockf -k "$lock" flyctl deploy \
  --app techtree-sh \
  --remote-only \
  --ha=false \
  --build-arg "TECHTREE_SOURCE_REVISION=$source_revision" \
  --build-arg "PREVIOUS_IMAGE=$previous_image" \
  "$@"

if ! curl -fsS -o /dev/null "https://techtree.sh$previous_script"; then
  echo "After the deploy, the previous release's $previous_script does not answer." >&2
  exit 1
fi

echo "The previous release's $previous_script still answers."
