#!/usr/bin/env bash
# The account checks of readiness: locks the machine's controls, then asks, as the tested account, whether it can read
# /work, use sudo, list the checkpoints or reach the management socket, and which harness version it runs. Prints one
# JSON object, {"account": {...}, "harness_version": "..."}; the bench compares it with what it expects.
#
# Usage: readiness.sh <harness_id>
set -euo pipefail
source /work/bin/machine/common.sh
lock
ACCOUNT=$(as_bench readiness.sh 2>/dev/null)
VERSION=$(runner version "$1" 2>/dev/null | head -1)
/.sprite/bin/python3 -c 'import json, sys; print(json.dumps({"account": json.loads(sys.argv[1]), "harness_version": sys.argv[2]}))' \
  "$ACCOUNT" "$VERSION"
