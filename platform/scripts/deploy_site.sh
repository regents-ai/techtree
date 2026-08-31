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

exec flyctl deploy \
  --app techtree-sh \
  --remote-only \
  --ha=false \
  --build-arg "TECHTREE_SOURCE_REVISION=$source_revision" \
  "$@"
