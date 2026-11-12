#!/usr/bin/env bash
# The live check (skills/regent-workflow, "Live checks"): techtree.sh read the way
# a visitor's and an agent's browser read it, never with raw curl.
#
#   make live-check                 the site should run this checkout's HEAD
#   make live-check COMMIT=<commit> the site should run that commit (after the
#                                   release record has been committed on top)
#
# Headless Chromium at 1280 and 390 wide, signed out (platform/assets/test/live):
# the live commit from /capabilities.json, every public page, the public
# documents, the browser tools the home page offers and every public read among
# them, and the Agent Message window. It writes nothing: no form is sent, no
# signed tool is called, and the pages start no visit (Global Privacy Control).
# Run it from a checkout of the live commit, or of the release record on top of
# it: the pages and tools are checked against this checkout's page list and tool
# manifest.
set -euo pipefail

live_url="https://techtree.sh"

root="$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)"
CHECKOUT_COMMIT="$(git -C "$root" rev-parse "${1:-HEAD}^{commit}")"
export CHECKOUT_COMMIT

cd "$root/platform/assets"
LIVE_URL="$live_url" npx playwright test --config playwright.live.config.ts
