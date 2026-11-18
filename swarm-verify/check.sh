#!/bin/sh
# Reruns the Swarm Verify checks (README.md beside this file).
#   check.sh           every model with Everystate, the two late-commit logs and the 128-worker run
#   check.sh tlc       also every model with TLC; needs Java 17 or later on PATH
#   check.sh measure   the measured limits; takes several minutes
#   check.sh fixtures  rewrites conformance/*.jsonl from sim/late_commit.py
set -eu
cd "$(dirname "$0")"

npm ci --ignore-scripts --no-audit --no-fund --loglevel=error
PYTHONDONTWRITEBYTECODE=1 uv run --no-project python check.py "$@"
