#!/usr/bin/env bash
# job.sh's background half. A Sprites machine pauses when nothing talks to it, which freezes running work; a task
# registered on the management socket keeps it awake. The task is renewed every minute for five, and deleted when the
# work ends. job.sh takes the first hold; a renewal Sprites refuses is kept in hold-errors.
set -uo pipefail
source /work/bin/machine/common.sh

NAME=$1
shift
J=$W/jobs/$NAME
# The boot id first: once job.sh sees a pid, it compares boot ids.
cat /proc/sys/kernel/random/boot_id > "$J/boot_id"
echo $$ > "$J/pid"

(
  while true; do
    sleep 60
    api -X PUT "http://sprite/v1/tasks/job-$NAME" -d '{"expire":"5m"}' > /dev/null 2>> "$J/hold-errors"
  done
) &
BEAT=$!

"$@" > "$J/log" 2>&1
CODE=$?

kill "$BEAT"
api -X DELETE "http://sprite/v1/tasks/job-$NAME" > /dev/null 2>> "$J/hold-errors"
echo "$CODE" > "$J/exit_code.tmp"
mv "$J/exit_code.tmp" "$J/exit_code"
