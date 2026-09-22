#!/usr/bin/env bash
# Build the release wheel from a clean, detached checkout of one commit.
#
# A wheel built in a working tree carries whatever that tree holds: an edited
# file, a stale generated artifact, a different build environment. The publish
# workflow rebuilds the wheel from the tag and refuses to publish unless the
# digest matches the approved one, so the approved wheel has to come from the
# same clean state the workflow will see. This script makes that the only way
# a release wheel is built: a temporary detached worktree of the exact commit,
# `uv build --wheel` in it, the digest printed, the worktree removed.
#
# Usage: tools/build_release_wheel.sh COMMIT OUTPUT_DIR
#
# Prints the wheel path and its SHA-256. OUTPUT_DIR must not already hold a
# wheel. Run it from anywhere inside the repository.

set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "usage: $0 COMMIT OUTPUT_DIR" >&2
  exit 2
fi

commit="$1"
output_dir="$2"

repository="$(git rev-parse --show-toplevel)"
resolved="$(git -C "$repository" rev-parse --verify "${commit}^{commit}")"

mkdir -p "$output_dir"
output_dir="$(cd "$output_dir" && pwd)"
if compgen -G "$output_dir/*.whl" > /dev/null; then
  echo "$output_dir already holds a wheel; choose an empty directory" >&2
  exit 1
fi

checkout="$(mktemp -d "${TMPDIR:-/tmp}/techtree-release-wheel.XXXXXX")"
cleanup() {
  git -C "$repository" worktree remove --force "$checkout" 2> /dev/null || true
  rmdir "$checkout" 2> /dev/null || true
}
trap cleanup EXIT

git -C "$repository" worktree add --detach --quiet "$checkout" "$resolved"

# The provenance hook stamps the commit the sources are at; a wheel from a
# detached HEAD names exactly the commit asked for.
(cd "$checkout/cli" && uv build --wheel --out-dir "$output_dir")

wheel="$(ls "$output_dir"/*.whl)"
digest="$(shasum -a 256 "$wheel" | awk '{print $1}')"
stamped="$(python3 - "$wheel" <<'PY'
import json, sys, zipfile
with zipfile.ZipFile(sys.argv[1]) as wheel:
    print(json.loads(wheel.read("techtree/resources/release/build-provenance.json"))["source_commit"])
PY
)"
if [ "$stamped" != "$resolved" ]; then
  echo "the wheel's provenance names $stamped, not $resolved" >&2
  exit 1
fi

echo "commit:  $resolved"
echo "wheel:   $wheel"
echo "sha256:  $digest"
