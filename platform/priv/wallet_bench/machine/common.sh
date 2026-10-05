# Shared by the machine scripts, which run as the machine's owner account. The tested harness runs as `bench`, which
# has no sudo and cannot read /work.
W=/work
ADMIN=/run/bench-admin

# Hides the machine's management controls from the tested account. Sprites mounts the last checkpoints under
# /.sprite/checkpoints and opens its management socket to every account; after a reset the "pre-restore" checkpoint
# holds the previous attempt's disk. The checkpoint folder becomes root-only, and the socket is bound into a root-only
# folder for `api` while its usual path is covered by an empty root-only file. Both reset when the machine boots, so
# every script that lets the tested account run anything calls this first.
lock() {
  sudo chmod 700 /.sprite/checkpoints
  if [ -S /.sprite/api.sock ]; then
    sudo install -d -m 700 "$ADMIN"
    sudo touch "$ADMIN/api.sock" "$ADMIN/closed"
    sudo chmod 000 "$ADMIN/closed"
    sudo mount --bind /.sprite/api.sock "$ADMIN/api.sock"
    sudo mount --bind "$ADMIN/closed" /.sprite/api.sock
  fi
}

# The machine's management API, through the socket only root can reach. Call `lock` first.
api() {
  sudo curl -sS --fail-with-body --unix-socket "$ADMIN/api.sock" -H 'Content-Type: application/json' "$@"
}

# Runs one of the scripts in machine/bench/ as the tested account, in a login shell from its home.
as_bench() {
  local script=$1
  shift
  sudo -u bench -H bash -lc "cd ~"$'\n'"$(cat "$W/bin/machine/bench/$script")" "$script" "$@"
}
