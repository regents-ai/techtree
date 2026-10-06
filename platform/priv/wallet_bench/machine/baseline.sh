#!/usr/bin/env bash
# Builds one harness's baseline, once, before the baseline checkpoint (the survey's baseline/baseline.sh). Runs as the
# machine's owner account through job.sh. The OpenAI key is not here: it arrives for each attempt (credentials.sh).
#
# Usage: baseline.sh <harness_id>
# Writes /work/baseline/: environment.txt, runner-install.log, harness-install.log, bench-inventory.txt and, last,
# manifest.json (what readiness and every attempt compare against).
set -euo pipefail
source /work/bin/machine/common.sh

HARNESS=${1:?harness id, e.g. H05}
OUT=$W/baseline
mkdir -p "$OUT"
lock

# 1. Environment facts (variable names only, never values).
{
  echo "captured_at=$(date -u +%FT%TZ)"
  echo "--- os-release"; cat /etc/os-release
  echo "--- uname"; uname -a
  echo "--- cpu/mem/disk"; nproc; free -b; df -B1 /
  echo "--- owner env names"; env | cut -d= -f1 | sort | tr '\n' ' '; echo
  echo "--- runtimes in /.sprite/bin"
  /.sprite/bin/node --version; /.sprite/bin/npm --version; /.sprite/bin/python3 --version
  /.sprite/bin/uv --version; /.sprite/bin/go version; /.sprite/bin/java -version; /.sprite/bin/bun --version
} > "$OUT/environment.txt" 2>&1

# 2. The model translator, not started.
bash "$W/bin/machine/proxy-install.sh" > "$OUT/proxy-install.log" 2>&1

# 3. The tested account: clean home, no sudo.
id bench > /dev/null 2>&1 || sudo useradd -m -s /bin/bash bench
sudo -u bench -H bash -c 'cat >> ~/.profile' <<'EOF'
# Benchmark baseline: Sprite-provided language runtimes (node, python3, uv, go, java, bun).
export PATH="$HOME/.local/bin:$PATH:/.sprite/bin"
EOF
sudo install -o bench -g bench -m 600 "$W/proxy/local.token" /home/bench/.model-token

# 4. The runner, then the harness through its Harbor adapter: the survey's pinned version and its wiring to the
# translator. /logs/agent keeps the agent's sessions and output for the whole attempt.
sudo env UV_PROJECT_ENVIRONMENT="$RUNNER_ENV" /.sprite/bin/uv sync --frozen --project "$W/bin/runner" \
  > "$OUT/runner-install.log" 2>&1
sudo mkdir -p /logs
sudo install -d -o bench -g bench -m 755 /logs/agent
runner setup "$HARNESS" > "$OUT/harness-install.log" 2>&1

# 5. The tested account before any wallet work.
as_bench inventory.sh > "$OUT/bench-inventory.txt" 2>&1

# 6. The manifest.
HARNESS_VERSION=$(runner version "$HARNESS" 2>/dev/null | head -1)
test -n "$HARNESS_VERSION"
/.sprite/bin/python3 - "$HARNESS" "$HARNESS_VERSION" > "$OUT/manifest.json" <<'EOF'
import json, os, platform, sys
release = dict(line.split("=", 1) for line in open("/etc/os-release").read().split("\n") if "=" in line)
print(json.dumps({
    "harness_id": sys.argv[1],
    "harness_version": sys.argv[2],
    "translator": "litellm 1.103.1",
    "model": "gpt-6-luna",
    "reasoning_effort": "high",
    "os": release.get("PRETTY_NAME", "").strip('"'),
    "kernel": platform.release(),
    "processors": os.cpu_count(),
    "memory_bytes": os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"),
}))
EOF
cat "$OUT/manifest.json"
