#!/usr/bin/env bash
# Fails unless this site is on the newest SIWA on both sides (Sean, 28 Oct 2026:
# "all sites should always be on the latest of siwa-server, forcibly"): the
# newest published regents-cli, which agents install to sign in and sign their
# requests, and the newest change to the SIWA library the server checks those
# requests with. Both are read from their sources on every run, so a new release
# stops every site's next gate until the site moves to it.
#
#   scripts/check-siwa-latest.sh <the Makefile's REGENTS_CLI_REV>
#
# regents-cli: the pin is the newest release's tag commit; the agent guide names
# the release, that commit and the wheel's SHA256; every install line and
# capabilities.json's cli.release name the release. The SIWA library: the
# elixir-utils commit platform/mix.exs pins contains the newest commit that
# changed siwa/siwa-elixir/apps/siwa on elixir-utils main. Needs `gh auth login`
# and curl.
set -euo pipefail

# Where this site keeps them. A site copying this script sets these three and keeps
# every check below the same.
guide=platform/priv/releases/climb-v0.7.28/bootstrap.json
install_lines=(plugin/README.md cli)
capabilities=platform/priv/tool_manifest.json

pin=$1
read -r latest wheel < <(curl -fsS https://pypi.org/pypi/regents-cli/json | python3 -I -c '
import json, sys
d = json.load(sys.stdin)
print(d["info"]["version"], next(u["digests"]["sha256"] for u in d["urls"] if u["packagetype"] == "bdist_wheel"))')
tag=$(gh api "repos/regents-ai/regents-cli/commits/v$latest" --jq .sha)
utils=$(sed -nE 's/^ *@elixir_utils_ref "([0-9a-f]{40})"$/\1/p' platform/mix.exs)
siwa=$(gh api "repos/regents-ai/elixir-utils/commits?path=siwa/siwa-elixir/apps/siwa&sha=main&per_page=1" --jq '.[0].sha')

failed=0
fail() {
  printf '%s\n' "$1" >&2
  failed=1
}

[ "$pin" = "$tag" ] ||
  fail "regents-cli $latest is the newest release: move REGENTS_CLI_REV in the Makefile from $pin to $tag."
for word in "regents-cli==$latest" "$tag" "$wheel"; do
  grep -qF "$word" "$guide" ||
    fail "regents-cli $latest is the newest release: $guide does not name $word."
done
stale=$(grep -rnoE 'regents-cli==[0-9]+(\.[0-9]+)*' "${install_lines[@]}" | grep -vE "==${latest//./\\.}\$" || true)
[ -z "$stale" ] || fail "regents-cli $latest is the newest release: these install lines name another release:
$stale"
release=$(python3 -I -c 'import json, sys; print(json.load(open(sys.argv[1]))["cli"]["release"])' "$capabilities")
[ "$release" = "$latest" ] ||
  fail "regents-cli $latest is the newest release: $capabilities names $release as cli.release."

if [ -z "$utils" ]; then
  fail "platform/mix.exs has no @elixir_utils_ref \"<40-character commit>\" line to check."
else
  case $(gh api "repos/regents-ai/elixir-utils/compare/$siwa...$utils" --jq .status) in
    identical | ahead) ;;
    *) fail "elixir-utils $siwa is the newest SIWA library change: move @elixir_utils_ref in platform/mix.exs from $utils to a commit that contains it." ;;
  esac
fi

exit "$failed"
