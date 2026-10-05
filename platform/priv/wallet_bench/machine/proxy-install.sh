#!/usr/bin/env bash
# The model translator: Anthropic- and OpenAI-format requests from the harness go to OpenAI as gpt-6-luna at
# reasoning effort high. It holds the real OpenAI key; the harness only gets a local token that works on 127.0.0.1.
# Installed with the baseline but not started: credentials.sh writes the key and starts it for each attempt.
#
# gpt-6-luna's list price (short context, per token) lets LiteLLM price every call for the spend cap in
# bench_hooks.py: input $0.10, cached input $0.01, output $0.50 per million tokens.
set -euo pipefail
source /work/bin/machine/common.sh
LITELLM_VERSION=1.103.1
P=$W/proxy

mkdir -p "$P"
chmod 700 "$P"
UV_TOOL_DIR=$P/uvtools UV_TOOL_BIN_DIR=$P/bin \
  /.sprite/bin/uv tool install --python 3.13 "litellm[proxy]==$LITELLM_VERSION"
"$P/bin/litellm" --version

cat > "$P/litellm.yaml" <<'EOF'
model_list:
  - model_name: "*"
    litellm_params:
      model: openai/gpt-6-luna
      api_key: os.environ/OPENAI_API_KEY
      reasoning_effort: high
      input_cost_per_token: 0.0000001
      cache_read_input_token_cost: 0.00000001
      output_cost_per_token: 0.0000005
litellm_settings:
  drop_params: true
  callbacks: bench_hooks.bench_hooks
general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
EOF
install -m 644 "$W/bin/machine/bench_hooks.py" "$P/bench_hooks.py"

# The translator's own output goes to a file under /work: Sprites' service logs can be read by every account.
cat > "$P/run.sh" <<'EOF'
#!/usr/bin/env bash
export OPENAI_API_KEY="$(cat /work/proxy/openai.key)"
export LITELLM_MASTER_KEY="$(cat /work/proxy/local.token)"
exec /work/proxy/bin/litellm --config /work/proxy/litellm.yaml --host 127.0.0.1 --port 4000 >> /work/proxy/litellm.log 2>&1
EOF
chmod 700 "$P/run.sh"
[ -s "$P/local.token" ] || (umask 077; printf 'sk-local-%s' "$(openssl rand -hex 16)" > "$P/local.token")
echo "translator $LITELLM_VERSION installed"
