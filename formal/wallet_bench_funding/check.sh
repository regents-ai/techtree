#!/bin/sh
# Reruns the Wallet Bench funding-cap model (README.md beside this file).
#   check.sh        typecheck, the four witness traces and random runs of the design as built; no Java
#   check.sh proof  also the Apalache proof for every depth; needs Java 17 or later on PATH
set -eu
cd "$(dirname "$0")"

quint() { npx --yes @informalsystems/quint@0.33.1 "$@"; }

quint typecheck funding.qnt

for model in code repeatable_read receipt_first stale_receipts; do
  quint test --main="$model" funding.qnt
done

quint run --main=code --invariant=Safe --max-samples=100000 --max-steps=40 --verbosity=1 funding.qnt

if [ "${1:-}" = proof ]; then
  quint verify --main=code --inductive-invariant=CodeInductive --invariant=Safe --verbosity=1 funding.qnt
fi
