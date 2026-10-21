#!/usr/bin/env python3
"""Run the template's change checks; unknown/build/dependency changes use make check."""

import argparse
import fcntl
import getpass
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import uuid


STOP_GRACE_SECONDS = 10

def changed_paths(root, base):
    def git(*args):
        return subprocess.check_output(["git", "-C", str(root), *args])

    revision = git("rev-parse", "--verify", f"{base}^{{commit}}").decode().strip()
    ancestor = git("merge-base", revision, "HEAD").decode().strip()
    # Include committed, staged, unstaged, deleted, renamed and new files. Comparing
    # at the common ancestor also retains our changes when remote main advances.
    tracked = git("diff", "--no-renames", "--name-only", "-z", ancestor)
    new = git("ls-files", "--others", "--exclude-standard", "-z")
    return sorted({p.decode() for p in (tracked + new).split(b"\0") if p})


def scope(paths):
    platform = False
    for path in paths:
        # These documents aren't compiled into the site. skills/, blog/ and priv/
        # deliberately aren't in this list: their content can change the pages.
        if path.startswith("docs/") or path in {"README.md", "CHANGELOG.md", "AGENTS.md"}:
            continue
        if path.startswith(("platform/lib/", "platform/test/", "platform/priv/")):
            if "/migrations/" in path or "/resource_snapshots/" in path:
                return "full"
            platform = True
        elif path.startswith("platform/assets/") and not path.endswith(
            ("package.json", "package-lock.json", "config.ts", "config.json")
        ):
            platform = True
        else:
            return "full"
    return "platform" if platform else "docs"


class Checks:
    def __init__(self, root, jobs):
        self.root = root
        self.platform = root / "platform"
        self.jobs = jobs
        self.partition = "_check_" + uuid.uuid4().hex[:12]
        self.children = []
        self.databases = set()
        self.locks = []
        self.tests_started = False
        self.tests_passed = False
        self.env = dict(os.environ)
        # Local checks must not inherit a production/staging database target or a
        # caller's real-auth lab mode. No settings file is loaded by this runner.
        for name in list(self.env):
            if name.startswith("DATABASE_") or name.endswith((
                "_DATABASE_CLUSTER_ID", "_DATABASE_CLUSTER_NAME", "_DATABASE_TARGET_MODE",
                "_LAB_AUTH", "_BROWSER_TEST", "_LAB",
            )) or name == "FLY_APP_NAME":
                self.env.pop(name)
        self.env.update(MIX_TEST_PARTITION=self.partition, PGHOST="127.0.0.1", PGPORT="5432",
                        PGUSER=getpass.getuser(), PATCHBAY_DB_HOST="127.0.0.1",
                        PATCHBAY_DB_USERNAME=getpass.getuser(),
                        REGENT_IDENTITY_TEST_DATABASE="regent_identity_test" + self.partition)
        self.env.pop("MIX_ENV", None)
        # A browser run must never borrow a caller's fixed port or shared database.
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = str(listener.getsockname()[1])
        self.env.update(PORT=port, TECHTREE_BROWSER_PORT=port,
                        TECHTREE_BROWSER_COPY=self.partition)

    def acquire(self):
        if shutil.disk_usage(self.root).free < 50 * 1024**3:
            raise RuntimeError("Less than 50 GiB free; finish and clean up owned runs first.")
        locks = Path(tempfile.gettempdir()) / f"regent-checks-{os.getuid()}"
        locks.mkdir(mode=0o700, exist_ok=True)
        # OS locks disappear on exit, including a crash. No waiting queue or lease.
        checkout = self.platform / "_build" / "check-change.lock"
        checkout.parent.mkdir(parents=True, exist_ok=True)
        self.lock(checkout)
        for index in range(2):
            try:
                self.lock(locks / f"slot-{index}")
                return
            except BlockingIOError:
                pass
        raise RuntimeError("Two check-change runs are active. Finish one before starting another.")

    def lock(self, path):
        handle = path.open("a")
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            raise
        self.locks.append(handle)

    def start(self, command, *, cwd=None, env=None, output=None):
        child = subprocess.Popen(command, cwd=cwd or self.platform, env=env or self.env,
                                 stdout=output, stderr=subprocess.STDOUT if output else None,
                                 start_new_session=True)
        self.children.append(child)
        return child

    def run(self, command, **kwargs):
        started = time.monotonic()
        print("==> " + " ".join(command), flush=True)
        status = self.start(command, **kwargs).wait()
        print(f"    {time.monotonic() - started:.1f}s; exit {status}", flush=True)
        if status:
            raise RuntimeError("Check failed: " + " ".join(command))

    def test_env(self, partition):
        return dict(self.env, MIX_ENV="test", MIX_TEST_PARTITION=partition)

    def elixir(self):
        self.run(["mix", "compile", "--warnings-as-errors"], env=self.test_env(self.partition))
        files = sorted(str(p.relative_to(self.platform))
                       for p in (self.platform / "test").rglob("*_test.exs"))
        if not files:
            raise RuntimeError("No ExUnit tests found; refusing an empty passing suite.")
        # Explicit disjoint file lists avoid the stale-manifest/partition interaction.
        # Don't launch an empty part: mix test with no files would run the whole suite.
        count = min(self.jobs, len(files))
        logs = self.platform / "_build" / "check-change" / self.partition
        logs.mkdir(parents=True)
        runs = []
        started = time.monotonic()
        for index in range(count):
            partition = f"{self.partition}p{index}"
            self.databases.add(partition)
            env = self.test_env(partition)
            self.run(["mix", "ecto.create", "--quiet"], env=env)
            log = logs / f"part-{index}.log"
            manifest = json.dumps(str(logs / f"part-{index}.failures"), ensure_ascii=False)
            configure = ("Application.ensure_loaded(:ex_unit); "
                         "Application.put_env(:ex_unit, :failures_manifest_path, " + manifest + ")")
            self.tests_started = True
            with log.open("w") as output:
                child = self.start(["mix", "do", "run", "--no-start", "-e", configure, "+",
                                    "test", "--warnings-as-errors", "--seed", "0",
                                    *files[index::count]], env=env, output=output)
            runs.append((child, log))
        failed = False
        for index, (child, log) in enumerate(runs):
            status = child.wait()
            print(f"==> ExUnit part {index + 1}/{count}; exit {status}", flush=True)
            print(log.read_text(), end="", flush=True)
            failed |= status != 0
        print(f"ExUnit total: {time.monotonic() - started:.1f}s", flush=True)
        if failed:
            raise RuntimeError(f"ExUnit failed; logs and per-part failure records: {logs}")
        self.tests_passed = True
        shutil.rmtree(logs)

    def check_platform(self):
        self.run(["mix", "esbuild.install", "--if-missing"])
        self.run(["mix", "check.static"])
        self.elixir()
        frontend = self.platform if (self.platform / "package.json").exists() else self.platform / "assets"
        scripts = json.loads((frontend / "package.json").read_text()).get("scripts", {})
        # Run the site's entire JS suite: import selection misses server-rendered
        # templates, CSS, fixtures and new untracked files.
        if "test" in scripts:
            self.run(["npm", "test"], cwd=frontend)
        if "test:browser" in scripts:
            self.databases.update({self.partition, self.partition + "_browser",
                                   "browser" + self.partition})
            self.run(["npm", "run", "test:browser"], cwd=frontend)
        else:
            print("GAP: this site has no configured browser walk; browser behavior is unverified.", flush=True)

    def cleanup(self):
        # Stop only our process groups, including grandchildren. Give browser
        # wrappers time to run their own teardown before escalating.
        groups = set()
        failed = False
        for child in self.children:
            try:
                os.killpg(child.pid, signal.SIGTERM)
                groups.add(child.pid)
            except ProcessLookupError:
                pass
            except PermissionError:
                groups.add(child.pid)
        deadline = time.monotonic() + STOP_GRACE_SECONDS
        while groups and time.monotonic() < deadline:
            for child in self.children:
                child.poll()
            for group in list(groups):
                try:
                    os.killpg(group, 0)
                except ProcessLookupError:
                    groups.remove(group)
                except PermissionError:
                    # Darwin can briefly report EPERM while a group exits.
                    # It is not evidence of disappearance; keep the deadline.
                    pass
            if groups:
                time.sleep(0.05)
        # A wrapper may exit before its descendants. Waiting on that wrapper
        # alone would leave a browser/server that ignored SIGTERM alive.
        for group in groups:
            try:
                os.killpg(group, 0)
                os.killpg(group, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except PermissionError:
                print(f"Could not confirm cleanup of owned process group {group}", file=sys.stderr)
                failed = True
        for child in self.children:
            try:
                child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                failed = True
        self.children.clear()
        if self.tests_started and not self.tests_passed and not failed:
            # Shards have private failure records. After failure or interruption,
            # the ordinary --failed command must not mistake a partial run for green.
            expression = ('Application.ensure_loaded(:ex_unit); '
                          'ExUnit.Filters.fail_all!(Path.join(Mix.Project.manifest_path(), ".mix_test_failures"))')
            status = subprocess.run(["mix", "run", "--no-start", "-e", expression],
                                    cwd=self.platform, env=self.test_env(self.partition)).returncode
            failed |= status != 0
        self.tests_started = False
        for partition in sorted(self.databases) if not failed else []:
            # The helper refuses anything except a loopback test database carrying
            # this run's random suffix. No production or pre-existing database.
            env = dict(self.test_env(partition), CHECK_CHANGE_RUN=self.partition)
            status = subprocess.run(["mix", "run", "--no-start", "scripts/check_change_cleanup.exs"],
                                    cwd=self.platform, env=env).returncode
            failed |= status != 0
        for handle in self.locks:
            handle.close()
        self.locks.clear()
        self.databases.clear()
        return failed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=os.environ.get("BASE", "origin/main"))
    parser.add_argument("--jobs", type=int, choices=range(1, 5), default=2)
    parser.add_argument("--plan", action="store_true", help="Show the selected checks without running them")
    parser.add_argument("--platform", action="store_true", help="Run all platform checks explicitly")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    paths = changed_paths(root, args.base)
    selected = "platform" if args.platform else scope(paths)
    print(f"Checks: {selected}; base: {args.base}; changed paths: {len(paths)}", flush=True)
    if args.plan or selected == "docs":
        if selected == "docs":
            print("No runtime changes selected. This is not release evidence.")
        return 0
    checks = Checks(root, args.jobs)
    status = 0

    def interrupted(signum, _frame):
        raise KeyboardInterrupt(f"signal {signum}")

    signal.signal(signal.SIGTERM, interrupted)
    try:
        checks.acquire()
        if selected == "full":
            checks.databases.update({checks.partition, checks.partition + "_browser",
                                     "browser" + checks.partition})
            checks.run(["make", "check"], cwd=root)
        else:
            checks.check_platform()
    except (RuntimeError, OSError, KeyboardInterrupt) as error:
        print(str(error), file=sys.stderr)
        status = 1
    finally:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        if checks.cleanup():
            print("Cleanup failed; the owned database needs attention.", file=sys.stderr)
            status = 1
    return status


if __name__ == "__main__":
    sys.exit(main())
