# Runs as the tested account (common.sh as_bench). The images the account saved since the turn started, such as T4's
# self-portrait: PNG, JPEG or WebP files in its home, outside caches and the agents' own folders, at most 5 MB each, the
# first five by path. Without an index, prints their paths; with one, prints that image's bytes. Reading as `bench`
# means only what the agent itself could read is ever copied.
# Usage: new-images.sh <turn_start_utc> [index]
START=$1 INDEX=${2:-}
mapfile -t images < <(find ~ -xdev -newermt "$START" -type f -size -5M \
  \( -iname "*.png" -o -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.webp" \) \
  -not -path "*/node_modules/*" -not -path "*/.cache/*" -not -path "*/.npm/*" -not -path "*/_npx/*" \
  -not -path "*/.local/share/*" -not -path "*/.claude/*" -not -path "*/.codex/*" -not -path "*/.hermes/*" \
  -not -path "*/.kilo*/*" -not -path "*/.pi/*" -not -path "*/.omp/*" -not -path "*/.opencode/*" \
  -not -path "*/.cline/*" -not -path "*/.deepseek*/*" -not -path "*/.config/*-agent/*" \
  -printf "%p\n" 2>/dev/null | grep -v $'\t' | sort | head -5)
if [ -z "$INDEX" ]; then
  printf "%s\n" "${images[@]}" | grep -v '^$'
else
  cat -- "${images[$INDEX]}"
fi
