# Runs as the tested account (common.sh as_bench). The survey's install check (bin/verify-install.sh): finds the
# wallet's executable, runs its help twice and its version, and lists what the account installed. Read-only.
# Usage: verify-install.sh <executable> <help_args...>
EXE=$1
shift
HELP="$*"
echo "captured_at=$(date -u +%FT%TZ)"
echo "--- which"
if P=$(command -v "$EXE"); then echo "$P"; readlink -f "$P"
else
  P=$(find ~ -name "$EXE" \( -type f -o -type l \) -perm -u+x \( -not -path "*/node_modules/*" -o -path "*/node_modules/.bin/*" \) 2>/dev/null | head -1)
  echo "NOT ON PATH in a login shell; found by search: ${P:-nothing}"
  P=${P:-$EXE}
fi
echo "--- help (exit)"; "$P" $HELP < /dev/null > /tmp/verify-help.txt 2>&1; echo "exit=$?"
if [ "$(wc -c < /tmp/verify-help.txt)" -le 2400 ]; then cat /tmp/verify-help.txt
else head -c 1000 /tmp/verify-help.txt; echo; echo "[... middle cut ...]"; tail -c 1400 /tmp/verify-help.txt; fi; echo
echo "--- second help (exit)"; "$P" $HELP < /dev/null > /dev/null 2>&1; echo "exit=$?"
echo "--- version attempts (exit)"
# The bare word "version" only when help lists it as a command: some wallet CLIs send loose words to their AI.
V="--version -V"; grep -qE "^\s+version\b" /tmp/verify-help.txt && V="$V version"
for v in $V; do echo "\$ $P $v"; timeout 20 "$P" $v < /dev/null 2>&1 | head -3; echo "exit=${PIPESTATUS[0]}"; done
echo "--- npm packages (bench prefixes)"
npm ls -g --depth=0 2>&1 | tail -n +1
for p in ~/.local ~/.npm-global; do test -d $p/lib/node_modules && npm ls -g --prefix $p --depth=0 2>&1; done
echo "--- uv tools"; uv tool list 2>&1
echo "--- pipx"; command -v pipx > /dev/null && pipx list --short 2>&1
echo "--- bench executables in ~/.local/bin, ~/bin, ~/.foundry/bin, ~/go/bin"
ls -la ~/.local/bin ~/bin ~/.foundry/bin ~/go/bin 2>/dev/null
echo "--- files owned by bench outside its home and the agent's log folder /logs/agent (expect none)"
find / -xdev -user bench -not -path "/home/bench" -not -path "/home/bench/*" -not -path "/proc/*" -not -path "/tmp/*" \
  -not -path /logs/agent -not -path "/logs/agent/*" 2>/dev/null | head -20
