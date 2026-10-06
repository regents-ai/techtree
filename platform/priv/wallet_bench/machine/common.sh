# Shared by the machine scripts, which run as the machine's owner account. The tested harness runs as `bench`, which
# has no sudo and cannot read /work.
W=/work
ADMIN=/run/bench-admin
# The runner's Python environment, built from runner/uv.lock at baseline, outside /work/bin so the recipe stays as sent.
RUNNER_ENV=/opt/awb-runner

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

# The bench's runner (runner/), as root: it drives the tested agent through its Harbor adapter, running the agent's
# own commands as `bench`. See runner/awb_runner/__main__.py for its commands.
runner() {
  sudo env PYTHONPATH="$W/bin/runner" PYTHONDONTWRITEBYTECODE=1 "$RUNNER_ENV/bin/python" -m awb_runner "$@"
}
