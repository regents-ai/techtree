#!/usr/bin/env bash
# Builds the committed tree into the release image and proves the image runs.
# Run it through `make release`, which runs every gate on that same tree first.
#
# The build context is `git archive` of HEAD's platform/ folder, with HEAD's
# blog/ folder as blog_content/ beside it, the same folders deploy_site.sh
# sends. Nothing uncommitted, ignored or outside this repository enters the
# image. The build reuses no cached layers, and the Dockerfile fetches every
# dependency at the version the lockfiles pin; the shared libraries'
# repositories are public, so the build takes no credentials.
#
# The smoke check starts the image against a throwaway PostgreSQL 17 on its own
# Docker network and removes both afterwards. It runs the release's migrate
# command against it, imports the catalog snapshot this tree added last on the
# stable channel, as production does, starts the server, and checks the health
# endpoint, the home page, a built stylesheet and the running server's
# database connection. The signing key and secret are thrown away with it.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"

commit="$(git rev-parse HEAD)"
image="techtree:${commit:0:12}"
run="techtree-smoke-$$"
context="$(mktemp -d)"
database_url="postgres://smoke:smoke@db/techtree_smoke"
catalog="$(git log -1 --no-renames --diff-filter=A --name-only --format= "$commit" -- platform/priv/catalog/sources | head -n 1 | cut -d/ -f5)"

cleanup() {
  status=$?
  if [[ $status -ne 0 ]] && docker container inspect "$run-app" >/dev/null 2>&1; then
    echo "Server log:" >&2
    docker logs --tail 40 "$run-app" >&2
  fi
  docker rm --force --volumes "$run-app" "$run-db" >/dev/null 2>&1 || true
  docker network rm "$run" >/dev/null 2>&1 || true
  rm -r "$context"
}
trap cleanup EXIT

# Retries a command once a second for up to a minute.
wait_for() {
  local what="$1"
  shift
  for _ in $(seq 60); do
    if "$@" >/dev/null 2>&1; then return; fi
    sleep 1
  done
  echo "Smoke check failed: $what did not answer within a minute." >&2
  exit 1
}

fail() {
  echo "Smoke check failed: $1" >&2
  exit 1
}

echo "==> Building $image from commit $commit"
git archive --format=tar "$commit:platform" | tar -x -C "$context"
git archive --format=tar --prefix=blog_content/ "$commit:blog" | tar -x -C "$context"
docker build --no-cache \
  --label "org.opencontainers.image.revision=$commit" \
  --build-arg "TECHTREE_SOURCE_REVISION=$commit" \
  --tag "$image" "$context"
digest="$(docker image inspect --format '{{.Id}}' "$image")"

echo "==> Starting a throwaway database"
docker network create --ipv6 "$run" >/dev/null
docker run --detach --name "$run-db" --network "$run" \
  --network-alias db \
  --env POSTGRES_USER=smoke --env POSTGRES_DB=techtree_smoke \
  --env POSTGRES_HOST_AUTH_METHOD=trust \
  docker.io/library/postgres:17 >/dev/null
wait_for "the database" docker exec "$run-db" pg_isready --quiet --host 127.0.0.1 --username smoke

release_env=(
  --network "$run"
  --env DATABASE_URL="$database_url"
  --env DATABASE_DIRECT_URL="$database_url"
  --env PHX_HOST=localhost
  --env SECRET_KEY_BASE="$(openssl rand -base64 48)"
  --env TECHTREE_NETWORK_SIGNING_KEY="$(openssl rand -base64 32)"
  --env TECHTREE_BOOTSTRAP_CHANNEL=stable
)

echo "==> Migrating the database and importing catalog $catalog with the release commands"
docker run --rm "${release_env[@]}" "$image" /app/bin/migrate
docker run --rm "${release_env[@]}" "$image" \
  /app/bin/techtree eval "Techtree.Release.import_catalog(\"$catalog\")"

echo "==> Starting the server"
docker run --detach --name "$run-app" "${release_env[@]}" --publish 127.0.0.1::4000 "$image" >/dev/null
base="http://$(docker port "$run-app" 4000/tcp | head -n 1)"
wait_for "the health endpoint" curl --silent --fail "$base/healthz"

health="$(curl --silent --fail "$base/healthz")"
[[ $health == *'"status":"ok"'* ]] || fail "the health endpoint answered $health"
[[ $health == *"\"deployed_source_revision\":\"$commit\""* ]] || fail "the server names another revision: $health"
[[ $health == *"\"source_revision\":\"$catalog\""* ]] || fail "the server serves another catalog: $health"

home="$(curl --silent --fail "$base/")"
stylesheet="$(grep -oE '/assets/[^"]+-[0-9a-f]{32}\.css' <<<"$home" | head -n 1)" ||
  fail "the home page links no fingerprinted stylesheet"
stylesheet_answer="$(curl --silent --fail --output /dev/null --write-out '%{http_code} %{content_type} %{size_download} bytes' "$base$stylesheet")"
[[ $stylesheet_answer == "200 text/css"* ]] || fail "$stylesheet answered $stylesheet_answer"

connected_database="$(docker exec "$run-app" /app/bin/techtree rpc \
  '[[name]] = Techtree.Repo.query!("SELECT current_database()").rows; IO.puts(name)')"
[[ $connected_database == techtree_smoke ]] || fail "the server's database answered \"$connected_database\""

pending="$(docker exec "$run-app" /app/bin/techtree rpc \
  'Techtree.Repo |> Ecto.Migrator.migrations() |> Enum.count(&match?({:down, _, _}, &1)) |> IO.puts()')"
[[ $pending == 0 ]] || fail "the database and the release disagree: $pending migrations pending"

echo
echo "Release built and smoke-checked"
echo "  app commit      $commit"
git show "$commit:platform/mix.lock" | grep -oE '\{:git, "[^"]+", "[0-9a-f]{40}"' | sort -u |
  sed -E 's/\{:git, "([^"]+)", "([0-9a-f]+)"/  shared library  \1 \2/'
echo "  image           $image"
echo "  image digest    $digest"
echo "  migrations      migrate succeeded; pending: $pending"
echo "  catalog         $catalog imported on stable"
echo "  health          $base/healthz answered ok for $commit"
echo "  static asset    $stylesheet answered $stylesheet_answer"
echo "  database        the running server queried $connected_database"
