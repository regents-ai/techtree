#!/usr/bin/env bash
# The account checks of readiness: locks the machine's controls and empties /tmp, then asks, as the tested account,
# whether it can read /work, use sudo, list the checkpoints or reach the management socket, and which harness version it
# runs. /tmp is a disk of its own that a restore leaves as the last attempt left it, so without emptying it one attempt
# would start among another's files. Prints one
# JSON object, {"account": {...}, "harness_version": "..."}; the bench compares it with what it expects.
#
# Usage: readiness.sh <harness_id>
set -euo pipefail
source /work/bin/machine/common.sh
lock
sudo find /tmp -mindepth 1 -delete
ACCOUNT=$(as_bench readiness.sh 2>/dev/null)
VERSION=$(runner version "$1" 2>/dev/null | head -1)
/.sprite/bin/python3 -c 'import json, sys; print(json.dumps({"account": json.loads(sys.argv[1]), "harness_version": sys.argv[2]}))' \
  "$ACCOUNT" "$VERSION"
