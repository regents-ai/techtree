#!/usr/bin/env bash
# Long work (a baseline build, a harness turn) in the background, so no connection has to stay open for it.
#
#   job.sh start <name> <command> [args...]   starts the work once; asking again only reports that it started
#   job.sh status <name>                       prints "running", "exit <code>", "lost" (the machine restarted or the
#                                              work died without an exit code) or "missing"
#
# Work lives in /work/jobs/<name>: command, pid, boot_id, log, exit_code, hold-errors. While it runs, a Sprites task
# keeps the machine from pausing (see job-run.sh). Sprites takes task names of lowercase letters, digits and dashes.
set -euo pipefail
source /work/bin/machine/common.sh

ACTION=$1 NAME=$2
J=$W/jobs/$NAME

case $ACTION in
  start)
    shift 2
    lock
    mkdir -p "$W/jobs"
    if mkdir "$J" 2>/dev/null; then
      # The work's first hold on the machine, taken here so a refused one stops the start with Sprites' answer.
      api -X PUT "http://sprite/v1/tasks/job-$NAME" -d '{"expire":"5m"}' >&2 || { rmdir "$J"; exit 1; }
      printf '%q ' "$@" > "$J/command"
      setsid nohup bash "$W/bin/machine/job-run.sh" "$NAME" "$@" < /dev/null > /dev/null 2>&1 &
    fi
    echo started
    ;;
  status)
    if [ -e "$J/exit_code" ]; then
      echo "exit $(cat "$J/exit_code")"
    elif [ ! -d "$J" ]; then
      echo missing
    elif [ ! -e "$J/pid" ]; then
      echo running
    elif [ "$(cat "$J/boot_id")" = "$(cat /proc/sys/kernel/random/boot_id)" ] && kill -0 "$(cat "$J/pid")" 2>/dev/null; then
      echo running
    elif [ -e "$J/exit_code" ]; then
      # It finished between the first look and this one.
      echo "exit $(cat "$J/exit_code")"
    else
      echo lost
    fi
    ;;
  *)
    echo "usage: job.sh start|status <name> ..." >&2
    exit 2
    ;;
esac
