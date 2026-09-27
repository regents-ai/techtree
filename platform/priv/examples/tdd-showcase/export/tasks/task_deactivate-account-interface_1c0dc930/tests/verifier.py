import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

APP = Path("/app")
ORIGINAL_IDS = {
    "test_accounts.AccountTests.test_create_can_be_fetched",
    "test_accounts.AccountTests.test_list_contains_created_accounts",
    "test_accounts.AccountTests.test_sign_in_returns_stored_account",
}

DISCOVER = r'''
import json
import sys
import unittest
sys.path.insert(0, "/app")
suite = unittest.defaultTestLoader.discover("/app/tests", pattern="test*.py", top_level_dir="/app/tests")
def flatten(item):
    for child in item:
        if isinstance(child, unittest.TestSuite):
            yield from flatten(child)
        else:
            yield child
print(json.dumps(sorted(case.id() for case in flatten(suite))))
'''

RUN_SELECTED = r'''
import json
import sys
import unittest
sys.path.insert(0, "/app")
wanted = set(json.loads(sys.argv[1]))
suite = unittest.defaultTestLoader.discover("/app/tests", pattern="test*.py", top_level_dir="/app/tests")
def flatten(item):
    for child in item:
        if isinstance(child, unittest.TestSuite):
            yield from flatten(child)
        else:
            yield child
selected = unittest.TestSuite(case for case in flatten(suite) if case.id() in wanted)
result = unittest.TextTestRunner(stream=sys.stderr, verbosity=0).run(selected)
sys.exit(0 if result.wasSuccessful() and result.testsRun == len(wanted) else 1)
'''

BEHAVIOR = r'''
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, "/app")
import accounts
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory) / "data.sqlite"
    accounts.open(path)
    first = accounts.create("alice@example.test", "secret")
    second = accounts.create("bob@example.test", "hunter2")
    assert accounts.fetch(first["id"]) == first
    assert accounts.deactivate(first["id"]) == first
    assert accounts.deactivate(first["id"]) == first
    assert accounts.fetch(first["id"]) == first
    assert first not in accounts.list_accounts()
    assert second in accounts.list_accounts()
    try:
        accounts.sign_in("alice@example.test", "secret")
    except accounts.AccountDeactivated:
        pass
    else:
        raise AssertionError("deactivated sign-in succeeded")
    accounts.open(path)
    assert first not in accounts.list_accounts()
    try:
        accounts.sign_in("alice@example.test", "secret")
    except accounts.AccountDeactivated:
        pass
    else:
        raise AssertionError("deactivation was not persistent")
    assert accounts.reactivate(first["id"]) == first
    assert accounts.reactivate(first["id"]) == first
    assert first in accounts.list_accounts()
    assert accounts.sign_in("alice@example.test", "secret") == first
    for operation in (accounts.deactivate, accounts.reactivate):
        try:
            operation(999999)
        except KeyError:
            pass
        else:
            raise AssertionError("unknown account did not raise KeyError")
'''


def command(script, *args, env=None):
    return subprocess.run(
        [sys.executable, "-c", script, *args],
        cwd=APP,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=20,
    )


def fail(message, detail=""):
    suffix = ""
    if detail:
        suffix = ": " + detail.strip().splitlines()[-1][:300]
    print(message + suffix)
    raise SystemExit(1)


behavior = command(BEHAVIOR)
if behavior.returncode != 0:
    fail("The submitted accounts package does not satisfy the ticket", behavior.stderr)

discovery = command(DISCOVER)
if discovery.returncode != 0:
    fail("The submitted test suite could not be loaded", discovery.stderr)
try:
    all_ids = set(json.loads(discovery.stdout.strip().splitlines()[-1]))
except Exception:
    fail("The submitted test suite did not produce discoverable unittest cases")
submitted = sorted(all_ids - ORIGINAL_IDS)
if not submitted:
    fail("No new deactivation tests were discovered")

own = command(RUN_SELECTED, json.dumps(submitted))
if own.returncode != 0:
    fail("The submitted deactivation tests fail against the submitted package", own.stderr)

package = APP / "accounts"
with tempfile.TemporaryDirectory(dir=APP) as holding:
    backup = Path(holding) / "accounts-original"
    shutil.move(package, backup)
    try:
        package.mkdir()
        shutil.copyfile("/tests/variant_accounts.py", package / "__init__.py")
        for mode, should_pass, description in (
            ("correct", True, "behavior-equivalent alternate implementation"),
            ("listing", False, "listing mutant"),
            ("signin", False, "sign-in mutant"),
            ("reactivate", False, "reactivation mutant"),
        ):
            env = os.environ.copy()
            env["ACCOUNT_VARIANT"] = mode
            result = command(RUN_SELECTED, json.dumps(submitted), env=env)
            if should_pass and result.returncode != 0:
                fail("Submitted tests do not survive the " + description, result.stderr)
            if not should_pass and result.returncode == 0:
                fail("Submitted tests did not detect the " + description)
    finally:
        shutil.rmtree(package, ignore_errors=True)
        shutil.move(backup, package)
