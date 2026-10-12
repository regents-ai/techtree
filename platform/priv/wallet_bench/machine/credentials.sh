#!/usr/bin/env bash
# The attempt's Claude key, on and off the machine.
#
#   credentials.sh attach   reads the key from standard input, writes it owner-only and starts the translator as a
#                           Sprites service; prints "attached" once it answers on 127.0.0.1:4000
#   credentials.sh revoke   deletes the service and the key file; prints "revoked" once both are gone. Revoke runs
#                           before every reset, so the "pre-restore" checkpoint Sprites keeps never holds the key.
set -euo pipefail
source /work/bin/machine/common.sh
P=$W/proxy

case $1 in
  attach)
    lock
    (umask 077; cat > "$P/anthropic.key")
    test -s "$P/anthropic.key"
    api -X PUT http://sprite/v1/services/llmproxy -d '{"cmd":"/work/proxy/run.sh"}' > /dev/null
    for _ in $(seq 1 90); do
      curl -sf http://127.0.0.1:4000/health/liveliness > /dev/null && break
      sleep 2
    done
    curl -sf http://127.0.0.1:4000/health/liveliness > /dev/null
    echo attached
    ;;
  revoke)
    lock
    if api http://sprite/v1/services | grep -q '"name":"llmproxy"'; then
      api -X DELETE http://sprite/v1/services/llmproxy > /dev/null
    fi
    if [ -e "$P/anthropic.key" ]; then shred -u "$P/anthropic.key"; fi
    test ! -e "$P/anthropic.key"
    ! pgrep -f /work/proxy/venv/bin/litellm > /dev/null
    echo revoked
    ;;
  *)
    echo "usage: credentials.sh attach|revoke" >&2
    exit 2
    ;;
esac
