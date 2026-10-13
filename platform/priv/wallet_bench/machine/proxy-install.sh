#!/usr/bin/env bash
# The model translator: Anthropic- and OpenAI-format requests from the harness go to Anthropic as claude-opus-5-5 with
# adaptive thinking at effort high. It holds the real Claude key; the harness only gets a local token that works on
# 127.0.0.1. Installed with the baseline but not started: credentials.sh writes the key and starts it for each attempt.
#
# claude-opus-5-5's list price lets LiteLLM price every call for the spend cap in bench_hooks.py: input $4, cache reads
# $0.20, five-minute cache writes $5 and output $20 per million tokens, with no long-prompt price.
#
# The harness's token reaches only the chat, Responses and Anthropic Messages routes the harnesses use, the
# Messages token counter and the model list. LiteLLM's other routes (forwarding straight to Anthropic, batches, files)
# would skip the spend cap. LiteLLM enforces this list without its paid licence and logs that it is a paid feature.
# LiteLLM sends each request once: its own retries would run after the failed call's hold is released. Harnesses
# retry with new requests, each of which takes its own hold. LiteLLM and every package it needs are installed from
# litellm-requirements.txt, each matched to its hashes.
set -euo pipefail
source /work/bin/machine/common.sh
LITELLM_VERSION=1.104.3
P=$W/proxy

mkdir -p "$P"
chmod 700 "$P"
/.sprite/bin/uv venv --python 3.13 "$P/venv"
/.sprite/bin/uv pip install --python "$P/venv/bin/python" --require-hashes -r "$W/bin/machine/litellm-requirements.txt"
"$P/venv/bin/litellm" --version | grep -F "$LITELLM_VERSION"

cat > "$P/litellm.yaml" <<'EOF'
model_list:
  - model_name: "*"
    litellm_params:
      model: anthropic/claude-opus-5-5
      api_key: os.environ/ANTHROPIC_API_KEY
      input_cost_per_token: 0.000004
      cache_read_input_token_cost: 0.0000002
      cache_creation_input_token_cost: 0.000005
      output_cost_per_token: 0.00002
litellm_settings:
  drop_params: true
  callbacks: bench_hooks.bench_hooks
router_settings:
  num_retries: 0
general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
  allowed_routes: ["/v1/chat/completions", "/v1/responses", "/v1/messages", "/v1/messages/count_tokens", "/v1/models"]
EOF
install -m 644 "$W/bin/machine/bench_hooks.py" "$P/bench_hooks.py"

# The translator's own output goes to a file under /work: Sprites' service logs can be read by every account.
cat > "$P/run.sh" <<'EOF'
#!/usr/bin/env bash
export ANTHROPIC_API_KEY="$(cat /work/proxy/anthropic.key)"
export LITELLM_MASTER_KEY="$(cat /work/proxy/local.token)"
exec /work/proxy/venv/bin/litellm --config /work/proxy/litellm.yaml --host 127.0.0.1 --port 4000 >> /work/proxy/litellm.log 2>&1
EOF
chmod 700 "$P/run.sh"
[ -s "$P/local.token" ] || (umask 077; printf 'sk-local-%s' "$(openssl rand -hex 16)" > "$P/local.token")
echo "translator $LITELLM_VERSION installed"
