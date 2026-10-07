# Runs as the tested account (common.sh as_bench). The survey's custody check (bin/verify-storage.sh): what the
# account created or changed since the turn started, outside caches, with names, sizes and permission modes only.
# Never prints file contents.
# Usage: verify-storage.sh <turn_start_utc>
START=$1
echo "captured_at=$(date -u +%FT%TZ) turn_start=$START"
echo "--- files in bench home created or changed since the turn started (caches excluded; mode owner size path)"
find ~ -xdev -newermt "$START" -type f \
  -not -path "*/node_modules/*" -not -path "*/.cache/*" -not -path "*/.npm/*" -not -path "*/_npx/*" \
  -not -path "*/.local/share/uv/*" -not -path "*/.local/share/pnpm/*" -not -path "*/go/pkg/*" \
  -not -path "*/.claude/*" -not -path "*/.codex/*" -not -path "*/.grok/*" -not -path "*/.muse/*" \
  -not -path "*/.hermes/*" -not -path "*/.kilo*/*" -not -path "*/.pi/*" -not -path "*/.omp/*" \
  -not -path "*/.opencode/*" -not -path "*/.local/share/opencode/*" -not -path "*/.cline/*" \
  -not -path "*/.deepseek*/*" -not -path "*/.ironclaw/*" -not -path "*/.config/*-agent/*" \
  -printf "%m %u %s %p\n" 2>/dev/null | sort -k4 | head -80
echo "--- same, outside bench home and the agent's log folder /logs/agent (expect none)"
find / -xdev -user bench -newermt "$START" -not -path /home/bench -not -path "/home/bench/*" -not -path "/proc/*" -not -path "/tmp/*" \
  -not -path /logs/agent -not -path "/logs/agent/*" \
  -printf "%m %u %s %p\n" 2>/dev/null | head -20
echo "--- bench processes still running"
ps -u bench -o etime=,args= | grep -v -E "^ *[0-9:]+ (-?bash|ps|grep|sort|head|cut)( |$)" | cut -c1-160 | head -20
