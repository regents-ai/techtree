#!/usr/bin/env bash
# Hands one prompt to the tested harness through the runner and records the whole turn under /work/turns/<turn_id>,
# then runs the survey's read-only checks of what the turn left behind. Runs as the owner account through job.sh; never
# repairs, installs or logs in.
#
# Usage: turn.sh <harness_id> <turn_id> <wall_cap_seconds> <resume_session_id | -> <executable> [help_args...]
#   expects the prompt at /work/turns/<turn_id>/prompt.txt. help_args default to --help.
#
# Writes into the turn folder: start_utc, stream.jsonl (the agent's own output), trajectory.json (Harbor's record of
# the turn), runner.log, exit_code, end_utc, wall_seconds, wall_cap_seconds, post-turn-inventory.txt, transcript.md,
# turn-summary.json, tool-calls.json, model-calls.jsonl, verify-install.txt, verify-storage.txt, images.txt with any
# images the agent saved in the turn (image-<n>.<type>, read as bench) and SHA256SUMS.
set -uo pipefail
source /work/bin/machine/common.sh

HARNESS=$1 TURN=$2 CAP=$3 RESUME=$4 EXE=$5
shift 5
HELP=("${@:---help}")
T=$W/turns/$TURN
test -s "$T/prompt.txt" || { echo "missing prompt for $TURN" >&2; exit 4; }
test ! -e "$T/exit_code" || { echo "turn $TURN already ran; a turn never runs twice" >&2; exit 3; }
lock

echo "$CAP" > "$T/wall_cap_seconds"
date -u +%FT%T.%3NZ > "$T/start_utc"
t0=$(date +%s.%N)
runner turn "$HARNESS" "$T" "$CAP" "$RESUME" > "$T/runner.log" 2>&1
echo $? > "$T/exit_code"
date -u +%FT%T.%3NZ > "$T/end_utc"
awk -v a="$t0" -v b="$(date +%s.%N)" 'BEGIN{printf "%.3f\n", b-a}' > "$T/wall_seconds"

as_bench post-turn-inventory.sh > "$T/post-turn-inventory.txt" 2>&1
runner transcript "$T" > /dev/null 2> "$T/transcript-errors.txt"
/.sprite/bin/python3 "$W/bin/machine/calls.py" "$T" > "$T/model-calls.jsonl"
as_bench verify-install.sh "$EXE" "${HELP[@]}" > "$T/verify-install.txt" 2>&1
as_bench verify-storage.sh "$(cat "$T/start_utc")" > "$T/verify-storage.txt" 2>&1
: > "$T/images.txt"
n=0
while IFS= read -r path; do
  ext=${path##*.}
  ext=${ext,,}
  as_bench new-images.sh "$(cat "$T/start_utc")" "$n" > "$T/image-$n.$ext" 2>/dev/null
  echo "image-$n.$ext $(sha256sum < "$T/image-$n.$ext" | cut -d' ' -f1) $(stat -c %s "$T/image-$n.$ext") $path | $(/.sprite/bin/python3 "$W/bin/machine/image_type.py" "$T/image-$n.$ext")" >> "$T/images.txt"
  n=$((n + 1))
done < <(as_bench new-images.sh "$(cat "$T/start_utc")")
(cd "$T" && sha256sum -- * > SHA256SUMS)
cat "$T/exit_code"
