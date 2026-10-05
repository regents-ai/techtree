#!/usr/bin/env bash
# Hands one prompt to the tested harness and records the whole turn under /work/turns/<turn_id> (the survey's
# bin/turn-remote.sh), then runs the survey's read-only checks of what the turn left behind. Runs as the owner account
# through job.sh; never repairs, installs or logs in.
#
# Usage: turn.sh <harness_id> <turn_id> <wall_cap_seconds> <resume_session_id | -> <executable> [help_args...]
#   expects the prompt at /work/turns/<turn_id>/prompt.txt. help_args default to --help.
#
# Writes into the turn folder: command.txt, start_utc, stream.jsonl, stderr.txt, exit_code, end_utc, wall_seconds,
# wall_cap_seconds, post-turn-inventory.txt, transcript.md, turn-summary.json, tool-calls.json, model-calls.jsonl,
# verify-install.txt, verify-storage.txt and SHA256SUMS.
set -uo pipefail
source /work/bin/machine/common.sh

HARNESS=$1 TURN=$2 CAP=$3 RESUME=$4 EXE=$5
shift 5
HELP=("${@:---help}")
[ "$RESUME" = "-" ] && RESUME=
T=$W/turns/$TURN
test -s "$T/prompt.txt" || { echo "missing prompt for $TURN" >&2; exit 4; }
test ! -e "$T/exit_code" || { echo "turn $TURN already ran; a turn never runs twice" >&2; exit 3; }
lock

source "$W/bin/harness/$HARNESS/turn.sh"
echo "$CMD" > "$T/command.txt"
echo "$CAP" > "$T/wall_cap_seconds"
date -u +%FT%T.%3NZ > "$T/start_utc"
t0=$(date +%s.%N)
sudo -u bench -H bash -lc "cd ~ && timeout --signal=INT --kill-after=30 $CAP $CMD" \
  < "$T/prompt.txt" > "$T/stream.jsonl" 2> "$T/stderr.txt"
echo $? > "$T/exit_code"
date -u +%FT%T.%3NZ > "$T/end_utc"
awk -v a="$t0" -v b="$(date +%s.%N)" 'BEGIN{printf "%.3f\n", b-a}' > "$T/wall_seconds"

as_bench post-turn-inventory.sh > "$T/post-turn-inventory.txt" 2>&1
/.sprite/bin/python3 "$W/bin/machine/transcript.py" "$T" "$HARNESS" > /dev/null 2> "$T/transcript-errors.txt"
/.sprite/bin/python3 "$W/bin/machine/calls.py" "$T" > "$T/model-calls.jsonl"
as_bench verify-install.sh "$EXE" "${HELP[@]}" > "$T/verify-install.txt" 2>&1
as_bench verify-storage.sh "$(cat "$T/start_utc")" > "$T/verify-storage.txt" 2>&1
(cd "$T" && sha256sum -- * > SHA256SUMS)
cat "$T/exit_code"
