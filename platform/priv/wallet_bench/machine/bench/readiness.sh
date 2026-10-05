# Runs as the tested account (common.sh as_bench). Each answer is true or false, and every one should be false.
yes_no() { if "$@" > /dev/null 2>&1; then echo true; else echo false; fi; }
printf '{"work_readable":%s,"sudo":%s,"checkpoints_listable":%s,"socket_reachable":%s}\n' \
  "$(yes_no ls /work)" \
  "$(yes_no sudo -n true)" \
  "$(yes_no ls /.sprite/checkpoints)" \
  "$(yes_no curl -s --max-time 5 --unix-socket /.sprite/api.sock http://sprite/v1/checkpoints)"
