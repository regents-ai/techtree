#!/bin/bash
set -u
mkdir -p /logs/verifier
printf '0\n' > /logs/verifier/reward.txt
if ! python /tests/verifier.py; then
    exit 0
fi
printf '1\n' > /logs/verifier/reward.txt
