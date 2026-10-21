#!/usr/bin/env bash
# Kept as the common entry point for existing Keyfleet callers.
set -euo pipefail
exec python3 "$(dirname "$0")/check-change.py" "$@"
