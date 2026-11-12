#!/usr/bin/env bash
# The live check (skills/regent-workflow, "Live checks"): techtree.sh read the way
# a visitor's and an agent's browser read it, and the way an agent reads it
# through the regents command line, never with raw curl.
#
#   make live-check                 the site should run this checkout's HEAD
#   make live-check COMMIT=<commit> the site should run that commit (after the
#                                   release record has been committed on top)
#
# First, headless Chromium at 1280 and 390 wide, signed out
# (platform/assets/test/live): the live commit from /capabilities.json, every
# public page, the public documents, the browser tools the home page offers and
# every public read among them, the Agent Message window, and the header's theme
# switch from a light-set and a dark-set device.
#
# Then two reads signed with this Mac's own agent key, in place, through the
# regents command line (Sean, 12 Nov 2026, 15 a): `regents techtree agents
# whoami` (GET /api/agents/v1/whoami) must name an agent signed in to this site
# and paired with a person's account, and `regents techtree account points`
# (GET /api/v1/account/points) must answer that person's Points with the fields
# cli/COMMANDS.md describes. regents renews the agent's Techtree sign-in when it
# has expired, and when the key is locked it asks for Touch ID on the page it
# names. Each read prints one pass or fail line and never its answer: no token,
# signature, key, wallet or account id. A missing regents, a refusal or an
# answer without those fields fails the check.
#
# It writes nothing: no form is sent, no signed tool is called in the browser,
# the pages start no visit (Global Privacy Control), and the signed reads change
# nothing but the time the site last saw the agent.
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

if ! command -v regents >/dev/null; then
  echo "✗ Signed reads: regents is not installed on this Mac (uv tool install regents-cli)."
  exit 1
fi

echo "Signed reads on $live_url as this Mac's agent ($(regents --version)):"

# One signed read: its name, the jq test its answer must pass, and what is wrong
# when it does not, then the command's words after `regents techtree`.
signed_read() {
  local name="$1" shape="$2" otherwise="$3" answer
  shift 3
  if ! answer="$(regents techtree "$@" --json --base-url "$live_url")"; then
    echo "  ✗ $name: $(jq -er '"refused, \(.error.code | strings): \(.error.message)"' <<<"$answer" 2>/dev/null || echo "regents gave no answer")"
    exit 1
  fi
  if ! jq -e "$shape" >/dev/null 2>&1 <<<"$answer"; then
    echo "  ✗ $name: $otherwise"
    exit 1
  fi
  echo "  ✓ $name"
}

signed_read "agents whoami" '
  .data.authenticated == true
  and .data.audience == "techtree"
  and (.data.agent.wallet | test("^0x[0-9a-f]{40}$"))
  and (.data.pairing | type == "object")' \
  "the answer does not show this Mac's agent signed in here and paired with a person's account." \
  agents whoami

signed_read "account points" '
  def decimal: type == "string" and test("^-?[0-9]+(\\.[0-9]+)?$");
  def rows($fields): type == "array" and all(.[]; . as $row | all($fields[]; . as $f | $row | has($f)));
  (.points | decimal) and (.earned_today | decimal) and (.earned_yesterday | decimal)
  and (.rank | type == "number" or . == null)
  and (.activity_being_verified | type == "number")
  and (.to_do | rows(["label", "repeats", "points", "done", "left", "today"]))
  and (.daily_limits | rows(["name", "limit", "remaining"]))
  and (.leaderboard | rows(["rank", "name", "wallet", "ens_name", "points", "you"]))
  and (.entries | rows(["label", "points", "status", "allowance_reduction", "by", "agent", "earned_at"]))
  and (.period_bonuses | rows(["period", "points", "nft_count", "bonus_percent"]))
  and (.more | type == "boolean")' \
  "the answer lacks fields cli/COMMANDS.md describes." \
  account points
