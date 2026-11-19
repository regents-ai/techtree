#!/usr/bin/env bash
# The live check, after each release: plain requests to techtree.sh, then two
# reads an agent signs through the regents command line.
#
#   make live-check                 the site should run this checkout's HEAD
#   make live-check COMMIT=<commit> the site should run that commit (after the
#                                   release record has been committed on top)
#
# First, plain requests with curl, signed out, each address once: no cookie is
# sent and none is kept, and every request sends Global Privacy Control, so none
# starts a visit. /capabilities.json must answer 200 and name the commit above
# as the one the site runs; every public page listed below must answer 200 with
# an HTML page; every public document listed below must answer 200. Each address
# prints one pass or fail line; every one is read before a failure stops the
# check, and the signed reads run only when all of them pass.
#
# Nothing is rendered (Sean, 19 Nov 2026, "delete all tests": the browser walk
# went with them). Page scripts, the browser tools the home page offers, the Agent Message window,
# the header's theme switch and the layout at phone width are not looked at, and
# neither are a page's console errors or the size of its press targets.
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
# It writes nothing: the requests send no form and start no visit, and the
# signed reads change nothing but the time the site last saw the agent. Run it
# from a checkout of the live commit, or of the release record on top of it.
set -euo pipefail

live_url="https://techtree.sh"

root="$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)"
checkout_commit="$(git -C "$root" rev-parse "${1:-HEAD}^{commit}")"

# Every public page whose address is the same on any Techtree, signed out.
pages=(/ /docs /docs/run-locally /docs/install /docs/test-a-skill /docs/api
  /docs/verify /docs/factory /results /wallet-bench /changelog /examples/tdd
  /services/skills /services/evals /services/environments /services/models
  /services/security /services/security/sample-report /services/swarm-verify
  /formal /account /account/agents /agents /agents/hermes /about /privacy /terms)

# The public documents beside them.
documents=(/healthz /api/v1/health /openapi.json /train.json /wallet-bench.json
  /skill.md /agents.md /llms.txt /sitemap.xml)

checked=0
failed=0

pass() {
  echo "  ✓ $1"
}

fail() {
  echo "  ✗ $1: $2"
  failed=$((failed + 1))
}

# One plain request: the address, then what its answer must be (capabilities,
# page or document). curl prints the body, then a last line with the status and
# the content type; when it fails, it says why on the line above.
read_address() {
  local path="$1" kind="$2" accept="*/*" answer last status type body live_commit
  checked=$((checked + 1))
  if [[ $kind == page ]]; then
    accept="text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
  fi
  if ! answer="$(curl --fail --silent --show-error --max-time 20 \
    --header "Accept: $accept" --header "Sec-GPC: 1" \
    --write-out '\n%{http_code} %{content_type}' "$live_url$path")"; then
    last="${answer##*$'\n'}"
    fail "$path" "status ${last%% *}"
    return
  fi
  last="${answer##*$'\n'}"
  status="${last%% *}"
  type="${last#* }"
  body="${answer%$'\n'*}"

  if [[ $status != 200 ]]; then
    fail "$path" "status $status"
  elif [[ $kind == page && ($type != text/html* || $body != *"</html>"*) ]]; then
    fail "$path" "status 200 without an HTML page ($type)"
  elif [[ $kind == capabilities ]]; then
    if ! live_commit="$(jq -er '.build.commit | strings' <<<"$body")"; then
      fail "$path" "names no build commit"
    elif [[ $live_commit != "$checkout_commit" ]]; then
      fail "$path" "the site runs $live_commit, not $checkout_commit; run it from a checkout of the live commit, or name it with COMMIT=<commit>"
    else
      pass "$path runs $live_commit"
    fi
  else
    pass "$path"
  fi
}

echo "Plain requests to $live_url, signed out:"
read_address /capabilities.json capabilities
for path in "${pages[@]}"; do
  read_address "$path" page
done
for path in "${documents[@]}"; do
  read_address "$path" document
done

if ((failed > 0)); then
  echo "  ✗ $failed of $checked addresses failed."
  exit 1
fi
echo "  ✓ $checked of $checked addresses answered."

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
