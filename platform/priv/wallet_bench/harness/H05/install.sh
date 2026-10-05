#!/usr/bin/env bash
# Claude Code for bench, pinned, talking Anthropic format to the local translator.
set -euo pipefail
CLAUDE_CODE_VERSION=2.1.286
W=/work
OUT=$W/baseline
curl -fsSL https://claude.ai/install.sh -o $W/baseline/claude-install.sh
sha256sum $W/baseline/claude-install.sh > "$OUT/claude-install.sha256"
sudo install -m 644 $W/baseline/claude-install.sh /tmp/claude-install.sh
sudo -u bench -H bash -lc "bash /tmp/claude-install.sh $CLAUDE_CODE_VERSION" >> "$OUT/harness-install.log" 2>&1
sudo -u bench -H bash -c 'cat >> ~/.profile' <<'EOF'
# Claude Code -> local translator -> OpenAI gpt-6-luna (reasoning effort high).
export ANTHROPIC_BASE_URL=http://127.0.0.1:4000
export ANTHROPIC_AUTH_TOKEN="$(cat ~/.model-token)"
export ANTHROPIC_MODEL=gpt-6-luna
export ANTHROPIC_DEFAULT_OPUS_MODEL=gpt-6-luna
export ANTHROPIC_DEFAULT_SONNET_MODEL=gpt-6-luna
export ANTHROPIC_DEFAULT_HAIKU_MODEL=gpt-6-luna
export CLAUDE_CODE_SUBAGENT_MODEL=gpt-6-luna
export DISABLE_TELEMETRY=1
EOF
sudo -u bench -H bash -lc 'claude --version' > "$OUT/harness-version.txt" 2>&1
