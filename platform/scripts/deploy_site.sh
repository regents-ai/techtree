#!/usr/bin/env bash
# Deploys the committed, pushed HEAD to techtree.sh. One Techtree deploy runs at
# a time; other sites' deploys never wait on it. The image is built first, with
# no shared lock, and only the switch to it takes one of the two places on the
# production database every site shares.
set -euo pipefail

repository_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repository_root"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Refusing to deploy: the working tree is not clean." >&2
  exit 1
fi

app="techtree-sh"
commit="$(git rev-parse HEAD)"
upstream_revision="$(git rev-parse '@{u}')"

if [[ "$commit" != "$upstream_revision" ]]; then
  echo "Refusing to deploy: HEAD has not been pushed to its upstream branch." >&2
  exit 1
fi

tag="main-${commit:0:12}"

# The switch to the new image runs the migrations and briefly adds a second
# machine's connections to the shared production database, which fits two
# switches at once. It takes whichever of the two places is free, or waits for
# the second.
switch() {
  local place=/tmp/regent-shared-db-release.lock
  lockf -k -s -t 0 "$place" true || place=/tmp/regent-shared-db-release-2.lock
  echo "==> Deploying registry.fly.io/$app:$tag (waits for $place if it is taken)"
  lockf -k "$place" flyctl deploy --app "$app" --image "registry.fly.io/$app:$tag" --ha=false
}

release() {
  # The live image, whose served files the new release keeps through the
  # rollover, and one of those files, asked for again once the deploy is done.
  local live_images previous_image live_page previous_script live_commit

  # Only the app group serves the site. A stopped app machine starts again on
  # its own image, so it counts; a destroyed one never serves again. One must be
  # started to show what is live, and each must name its image.
  if ! live_images="$(flyctl machine list --app "$app" --json | jq -er '
    [.[] | select(.config.metadata.fly_process_group == "app" and .state != "destroyed" and .state != "destroying")]
    | select(any(.[]; .state == "started") and all(.[]; .image_ref | .registry and .repository and .digest))
    | map(.image_ref | "\(.registry)/\(.repository)@\(.digest)") | unique | .[]')"; then
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

  echo "==> Building registry.fly.io/$app:$tag from commit $commit"
  flyctl deploy \
    --app "$app" \
    --build-only \
    --push \
    --remote-only \
    --image-label "$tag" \
    --build-arg "SOURCE_COMMIT=$commit" \
    --build-arg "PREVIOUS_IMAGE=$previous_image" \
    "$@"

  switch

  # The blue-green switch (fly.toml) returns only once the old machines are
  # gone, so the site already answers with the new release's commit.
  if ! live_commit="$(curl -fsS https://techtree.sh/capabilities.json | jq -er .build.commit)"; then
    echo "After the deploy, techtree.sh/capabilities.json can't be read, so the release is not proved live." >&2
    exit 1
  fi

  if [[ "$live_commit" != "$commit" ]]; then
    echo "After the deploy, techtree.sh reports commit $live_commit, not $commit." >&2
    exit 1
  fi

  echo "techtree.sh reports commit $commit."

  if ! curl -fsS -o /dev/null "https://techtree.sh$previous_script"; then
    echo "After the deploy, the previous release's $previous_script does not answer." >&2
    exit 1
  fi

  echo "The previous release's $previous_script still answers."
}

lock="/tmp/regent-release-$app.lock"
echo "==> Deploying ${commit:0:7} to $app (waits for any other Techtree deploy holding $lock)"
export app commit tag
export -f release switch
lockf -k "$lock" bash -euo pipefail -c 'release "$@"' release "$@"
