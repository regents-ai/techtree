# Runs as the tested account (common.sh as_bench). A passive, read-only snapshot right after a turn; no repairs.
echo "captured_at=$(date -u +%FT%TZ)"
echo "--- wallet CLIs on PATH"
for c in bankr mm mp cdp awal phantom cast ape circle safe-cli web3signer zerion splits paw wdk turnkey ethkit fireblocks; do command -v $c; done
echo "--- npm global packages (bench)"; npm ls -g --depth=0 2>&1
echo "--- home tree (depth 3)"; find . -maxdepth 3 -not -path "./.local/share/claude/versions/*" -not -path "./.npm/_cacache/*" | sort
