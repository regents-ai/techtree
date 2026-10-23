"""Exercise selection, process failures and owned cleanup without a product database."""

import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "check-change.py"
spec = importlib.util.spec_from_file_location("check_change", SOURCE)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class Selection(unittest.TestCase):
    def test_server_pages_and_new_assets_require_the_browser(self):
        for path in ["platform/lib/web/page.html.heex", "platform/lib/app.ex",
                     "platform/priv/public/help.md", "platform/assets/css/app.css",
                     "platform/assets/js/new.ts", "platform/test/browser/new.spec.ts"]:
            with self.subTest(path=path):
                self.assertEqual(runner.scope([path]), "platform")

    def test_unknown_shared_dependencies_and_runner_changes_require_full_check(self):
        for path in ["platform/mix.lock", "platform/config/config.exs", "Makefile",
                     "platform/assets/package-lock.json", "skills/build/SKILL.md",
                     "scripts/check-change.py", "identity/lib/account.ex",
                     "platform/priv/repo/migrations/123.exs", "contracts/src/Token.sol",
                     "platform/graph_host/src/main.py", "blog/post.md"]:
            with self.subTest(path=path):
                self.assertEqual(runner.scope([path]), "full")

    def test_docs_dont_claim_a_runtime_check(self):
        self.assertEqual(runner.scope(["docs/design.md", "README.md"]), "docs")

    def test_git_includes_staged_unstaged_new_deleted_and_branch_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def git(*args):
                return subprocess.check_output(["git", "-C", directory, *args], stderr=subprocess.DEVNULL)
            git("init")
            git("config", "user.email", "fixture@example.invalid")
            git("config", "user.name", "Fixture")
            for name in ["staged", "unstaged", "deleted", "renamed"]:
                (root / name).write_text("before\n")
            git("add", ".")
            git("commit", "-m", "base")
            git("branch", "base")
            (root / "committed").write_text("branch\n")
            git("add", ".")
            git("commit", "-m", "branch change")
            (root / "staged").write_text("after\n")
            git("add", "staged")
            (root / "unstaged").write_text("after\n")
            (root / "new file").write_text("new\n")
            (root / "deleted").unlink()
            git("mv", "renamed", "new name")
            self.assertEqual(set(runner.changed_paths(root, "base")),
                             {"staged", "unstaged", "new file", "deleted",
                              "renamed", "new name", "committed"})
            with self.assertRaises(subprocess.CalledProcessError):
                runner.changed_paths(root, "missing-base")


class Execution(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.platform = self.root / "platform"
        (self.platform / "test").mkdir(parents=True)
        for name in ["a_test.exs", "b_test.exs", "space name_test.exs"]:
            (self.platform / "test" / name).write_text("fixture")
        (self.platform / "package.json").write_text(json.dumps({"scripts": {
            "test": "vitest run", "test:browser": "playwright test"}}))
        binary = self.root / "bin"
        binary.mkdir()
        self.record = self.root / "calls.jsonl"
        stub = '''#!/usr/bin/env python3
import json, os, sys, time
with open(os.environ["CHECK_FIXTURE_LOG"], "a") as f:
    f.write(json.dumps([os.path.basename(sys.argv[0]), sys.argv[1:], os.environ.get("MIX_TEST_PARTITION"), os.environ.get("MIX_ENV")]) + "\\n")
if os.environ.get("CHECK_FIXTURE_SLEEP") and "test" in sys.argv[1:]:
    time.sleep(30)
if os.environ.get("CHECK_FIXTURE_FAIL") and any("b_test.exs" in a for a in sys.argv):
    sys.exit(7)
'''
        for name in ["mix", "npm", "make"]:
            (binary / name).write_text(stub)
            (binary / name).chmod(0o755)
        self.environment = patch.dict(os.environ, {
            "PATH": str(binary) + os.pathsep + os.environ["PATH"],
            "CHECK_FIXTURE_LOG": str(self.record),
        })
        self.environment.start()
        self.checks = runner.Checks(self.root, 4)

    def tearDown(self):
        self.checks.cleanup()
        self.environment.stop()
        self.temporary.cleanup()

    def calls(self):
        return [json.loads(line) for line in self.record.read_text().splitlines()]

    def test_all_files_run_once_even_with_more_jobs_than_files(self):
        self.checks.check_platform()
        calls = self.calls()
        parts = [args for tool, args, _, _ in calls if tool == "mix" and "test" in args]
        files = [arg for args in parts for arg in args if arg.endswith("_test.exs")]
        self.assertEqual(len(parts), 3)
        self.assertEqual(sorted(files), ["test/a_test.exs", "test/b_test.exs", "test/space name_test.exs"])
        self.assertTrue(any(tool == "npm" and "test:browser" in args for tool, args, _, _ in calls))

    def test_part_failure_cannot_report_success_or_launch_browser(self):
        with patch.dict(os.environ, CHECK_FIXTURE_FAIL="1"):
            self.checks.env["CHECK_FIXTURE_FAIL"] = "1"
            with self.assertRaisesRegex(RuntimeError, "ExUnit failed"):
                self.checks.check_platform()
        self.assertFalse(any(tool == "npm" for tool, _, _, _ in self.calls()))
        partitions = set(self.checks.databases)
        self.assertFalse(self.checks.cleanup())
        cleaned = {partition for tool, args, partition, env in self.calls()
                   if "scripts/check_change_cleanup.exs" in args and env == "test"}
        self.assertEqual(cleaned, partitions)
        self.checks.databases.clear()

    def test_cleanup_stops_owned_process(self):
        child = self.checks.start(["mix", "test"], env=dict(self.checks.env, CHECK_FIXTURE_SLEEP="1"))
        self.checks.cleanup()
        self.assertIsNotNone(child.poll())

    def test_cleanup_stops_descendant_after_wrapper_exits(self):
        pidfile = self.root / "descendant.pid"
        code = '''import os, signal, sys, time
if os.fork() == 0:
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    with open(sys.argv[1], "w") as f: f.write(str(os.getpid()))
    time.sleep(60)
'''
        child = self.checks.start([sys.executable, "-c", code, str(pidfile)])
        child.wait()
        deadline = time.monotonic() + 3
        while not pidfile.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(pidfile.exists())
        pid = int(pidfile.read_text())
        try:
            with patch.object(runner, "STOP_GRACE_SECONDS", 0.1):
                self.checks.cleanup()
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    break
                time.sleep(0.01)
            else:
                self.fail("owned descendant survived cleanup")
        finally:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def test_empty_suite_fails(self):
        for path in (self.platform / "test").iterdir():
            path.unlink()
        with self.assertRaisesRegex(RuntimeError, "No ExUnit tests"):
            self.checks.elixir()

    def test_caller_cannot_redirect_test_databases(self):
        with patch.dict(os.environ, {"DATABASE_URL": "postgres://remote.invalid/production",
                                    "PATCHBAY_DB_HOST": "remote.invalid",
                                    "REGENT_IDENTITY_TEST_DATABASE": "preexisting",
                                    "ASH_TEMPLATE_DATABASE_CLUSTER_ID": "remote-cluster",
                                    "AUTOLAUNCH_LAB_AUTH": "privy"}):
            checks = runner.Checks(self.root, 2)
        self.assertNotIn("DATABASE_URL", checks.env)
        self.assertNotIn("ASH_TEMPLATE_DATABASE_CLUSTER_ID", checks.env)
        self.assertNotIn("AUTOLAUNCH_LAB_AUTH", checks.env)
        self.assertEqual(checks.env["PATCHBAY_DB_HOST"], "127.0.0.1")
        self.assertEqual(checks.env["REGENT_IDENTITY_TEST_DATABASE"],
                         "regent_identity_test" + checks.partition)

    def test_cleanup_failure_is_reported(self):
        self.checks.databases.add(self.checks.partition)
        with patch.object(subprocess, "run", return_value=subprocess.CompletedProcess([], 1)):
            self.assertTrue(self.checks.cleanup())
        self.checks.databases.clear()


class Capacity(unittest.TestCase):
    def test_checkout_and_machine_limits_release_their_capacity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checks = [runner.Checks(root / str(index), 2) for index in range(3)]
            duplicate = runner.Checks(root / "0", 2)
            usage = SimpleNamespace(free=200 * 1024**3)
            with patch.object(runner.tempfile, "gettempdir", return_value=directory), \
                    patch.object(runner.shutil, "disk_usage", return_value=usage):
                try:
                    checks[0].acquire()
                    with self.assertRaises(BlockingIOError):
                        duplicate.acquire()
                    checks[1].acquire()
                    with self.assertRaisesRegex(RuntimeError, "Two check-change runs"):
                        checks[2].acquire()
                    checks[2].cleanup()
                    checks[0].cleanup()
                    checks[2].acquire()
                finally:
                    for check in [*checks, duplicate]:
                        check.cleanup()


class FailureManifest(unittest.TestCase):
    def test_failed_shard_then_passing_shard_does_not_hide_failure(self):
        # A real, dependency-free Mix fixture exercises ExUnit's failure records.
        # Its ecto.create alias is intentionally empty: it uses no database.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            platform = root / "platform"
            (platform / "test").mkdir(parents=True)
            (platform / "scripts").mkdir()
            (platform / "mix.exs").write_text('''defmodule CheckFixture.MixProject do
  use Mix.Project
  def project, do: [app: :check_fixture, version: "0.1.0", aliases: ["ecto.create": &empty/1]]
  defp empty(_), do: :ok
end
''')
            (platform / "test/test_helper.exs").write_text("ExUnit.start()\n")
            (platform / "scripts/check_change_cleanup.exs").write_text("# No database in this fixture.\n")
            (platform / "test/a_test.exs").write_text('''defmodule FailureTest do
  use ExUnit.Case
  test "fails", do: assert(false)
end
''')
            (platform / "test/b_test.exs").write_text('''defmodule PassingTest do
  use ExUnit.Case
  test "finishes last" do
    Process.sleep(250)
    assert true
  end
end
''')
            checks = runner.Checks(root, 2)
            try:
                with self.assertRaisesRegex(RuntimeError, "ExUnit failed"):
                    checks.elixir()
            finally:
                self.assertFalse(checks.cleanup())
            retry = subprocess.run(["mix", "test", "--failed", "--seed", "0"], cwd=platform,
                                   env=dict(os.environ, MIX_ENV="test"), capture_output=True, text=True)
            self.assertNotEqual(retry.returncode, 0, retry.stdout + retry.stderr)
            self.assertIn("Result: 1/2 passed", retry.stdout)


if __name__ == "__main__":
    unittest.main()
