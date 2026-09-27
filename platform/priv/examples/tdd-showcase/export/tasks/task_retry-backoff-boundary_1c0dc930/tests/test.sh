#!/bin/bash
mkdir -p /logs/verifier
python3 - <<'PY'
import ast
import importlib
import os
from pathlib import Path
import subprocess
import sys
import time

REWARD = Path("/logs/verifier/reward.txt")
APP = Path("/app")
SERVICE_PATH = APP / "notifier" / "service.py"
BACKOFF_PATH = APP / "notifier" / "backoff.py"
RUNNER_PATH = APP / ".techtree_test_runner.py"


def finish(ok, message=None):
    REWARD.write_text("1\n" if ok else "0\n")
    if not ok:
        print(message or "verification failed")


def binding_expressions(source):
    tree = ast.parse(source)
    time_modules = set()
    sleep_names = set()
    backoff_modules = set()
    policy_names = set()

    for node in tree.body:
        if isinstance(node, ast.Import):
            for item in node.names:
                bound = item.asname or item.name.split(".")[0]
                if item.name == "time":
                    time_modules.add(bound)
                if item.name in {"notifier.backoff", "backoff"}:
                    backoff_modules.add(bound)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for item in node.names:
                bound = item.asname or item.name
                if module == "time" and item.name == "sleep":
                    sleep_names.add(bound)
                if module.endswith("backoff") and item.name == "delay_for_retry":
                    policy_names.add(bound)
                if module in {"", "notifier"} and item.name == "backoff":
                    backoff_modules.add(bound)
        elif isinstance(node, ast.Assign):
            value = node.value
            is_sleep = (
                isinstance(value, ast.Attribute)
                and value.attr == "sleep"
                and isinstance(value.value, ast.Name)
                and value.value.id in time_modules
            ) or (isinstance(value, ast.Name) and value.id in sleep_names)
            if is_sleep:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        sleep_names.add(target.id)

    sleep_expr = None
    policy_expr = None
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            if func.attr == "sleep" and func.value.id in time_modules:
                sleep_expr = f"globals()[{func.value.id!r}].sleep"
            if func.attr == "delay_for_retry" and func.value.id in backoff_modules:
                policy_expr = f"globals()[{func.value.id!r}].delay_for_retry"
        elif isinstance(func, ast.Name):
            if func.id in sleep_names:
                sleep_expr = f"globals()[{func.id!r}]"
            if func.id in policy_names:
                policy_expr = f"globals()[{func.id!r}]"

    if sleep_expr is None:
        sleep_expr = "__import__('time').sleep"
    if policy_expr is None:
        policy_expr = "__import__('notifier.backoff', fromlist=['delay_for_retry']).delay_for_retry"
    return sleep_expr, policy_expr


def mutant_suffix(source, kind):
    sleep_expr, policy_expr = binding_expressions(source)
    if kind == "extra_retry":
        caught = "_MutTemporaryFailure"
        limit = 5
        delay = "_mutant_policy(retries)"
    elif kind == "wrong_wait":
        caught = "_MutTemporaryFailure"
        limit = 4
        delay = "_mutant_policy(retries) + 0.5"
    else:
        caught = "(_MutTemporaryFailure, _MutPermanentFailure)"
        limit = 4
        delay = "_mutant_policy(retries)"

    return f'''

# verifier-installed behavioral mutant
import inspect as _mut_inspect
from notifier.errors import TemporaryFailure as _MutTemporaryFailure
from notifier.errors import PermanentFailure as _MutPermanentFailure

_mut_signature = _mut_inspect.signature(send)
_mut_sleep_parameters = [
    parameter.name
    for parameter in _mut_signature.parameters.values()
    if parameter.default is __import__('time').sleep
]

def _mutant_sleep(seconds):
    return ({sleep_expr})(seconds)

def _mutant_policy(retry_number):
    return ({policy_expr})(retry_number)

def send(message, client, *args, **kwargs):
    pause = _mutant_sleep
    if _mut_sleep_parameters:
        bound = _mut_signature.bind(message, client, *args, **kwargs)
        bound.apply_defaults()
        pause = bound.arguments[_mut_sleep_parameters[0]]
    retries = 0
    while True:
        pause(globals().get("RATE_LIMIT_SECONDS", 0.05))
        try:
            return client.send(message)
        except {caught}:
            if retries >= {limit}:
                raise
            retries += 1
            pause({delay})
'''


RUNNER_PATH.write_text(r'''import importlib
import inspect
import socket
import sys
import types
import unittest

violations = []
policy = importlib.import_module("notifier.backoff")
service = importlib.import_module("notifier.service")

policy_owned = {
    name: value
    for name, value in vars(policy).items()
    if (inspect.isfunction(value) or inspect.isclass(value))
    and getattr(value, "__module__", None) == policy.__name__
}
owned_ids = {id(value) for value in policy_owned.values()}
service_owned = {
    name: value for name, value in vars(service).items() if id(value) in owned_ids
}

class GuardedPolicy(types.ModuleType):
    def __setattr__(self, name, value):
        if name in policy_owned and value is not policy_owned[name]:
            violations.append("backoff policy replacement")
        return super().__setattr__(name, value)

class GuardedService(types.ModuleType):
    def __setattr__(self, name, value):
        if name in service_owned and value is not service_owned[name]:
            violations.append("backoff policy alias replacement")
        return super().__setattr__(name, value)

policy.__class__ = GuardedPolicy
service.__class__ = GuardedService

class BlockedSocket:
    def __init__(self, *args, **kwargs):
        raise AssertionError("network access is disabled during the test suite")

def blocked_connection(*args, **kwargs):
    raise AssertionError("network access is disabled during the test suite")

socket.socket = BlockedSocket
socket.create_connection = blocked_connection

suite = unittest.defaultTestLoader.discover("/app/tests", pattern="test*.py")
result = unittest.TextTestRunner(stream=sys.stdout, verbosity=1).run(suite)
if violations:
    print("submitted tests replaced a project-owned backoff collaborator")
    raise SystemExit(2)
raise SystemExit(0 if result.wasSuccessful() else 1)
''')


def run_suite(label, should_pass):
    env = os.environ.copy()
    env["PYTHONPATH"] = "/app"
    started = time.monotonic()
    try:
        result = subprocess.run(
            [sys.executable, str(RUNNER_PATH)],
            cwd="/app",
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=5.0,
        )
    except subprocess.TimeoutExpired:
        return False, f"submitted tests exceeded five seconds for {label}"
    elapsed = time.monotonic() - started
    if elapsed >= 5.0:
        return False, f"submitted tests exceeded five seconds for {label}"
    passed = result.returncode == 0
    if should_pass and not passed:
        if result.returncode == 2:
            return False, "submitted tests replace the project-owned backoff policy"
        return False, f"submitted tests failed for {label}"
    if not should_pass and passed:
        return False, f"submitted tests did not detect the {label} mutant"
    return True, None


def verify_behavior():
    for name in list(sys.modules):
        if name == "notifier" or name.startswith("notifier."):
            del sys.modules[name]
    service = importlib.import_module("notifier.service")
    errors = importlib.import_module("notifier.errors")

    original_sleep = time.sleep
    replaced_aliases = {}
    waits = []

    def fake_sleep(seconds):
        waits.append(seconds)

    for name, value in list(vars(service).items()):
        if value is original_sleep:
            replaced_aliases[name] = value
            setattr(service, name, fake_sleep)
    replaced_defaults = []
    for value in list(vars(service).values()):
        if not callable(value) or getattr(value, "__module__", None) != service.__name__:
            continue
        defaults = getattr(value, "__defaults__", None)
        kwdefaults = getattr(value, "__kwdefaults__", None)
        if defaults and any(item is original_sleep for item in defaults):
            replaced_defaults.append((value, "__defaults__", defaults))
            value.__defaults__ = tuple(fake_sleep if item is original_sleep else item for item in defaults)
        if kwdefaults and any(item is original_sleep for item in kwdefaults.values()):
            replaced_defaults.append((value, "__kwdefaults__", kwdefaults))
            value.__kwdefaults__ = {key: fake_sleep if item is original_sleep else item for key, item in kwdefaults.items()}
    time.sleep = fake_sleep

    class Client:
        def __init__(self, outcomes):
            self.outcomes = list(outcomes)
            self.calls = []

        def send(self, message):
            self.calls.append(message)
            outcome = self.outcomes.pop(0)
            if isinstance(outcome, BaseException):
                raise outcome
            return outcome

    try:
        rate = service.RATE_LIMIT_SECONDS
        delays = [2, 4, 8, 16]

        for temporary_failures in range(5):
            waits.clear()
            outcomes = [errors.TemporaryFailure(f"temporary-{n}") for n in range(temporary_failures)] + ["accepted"]
            client = Client(outcomes)
            result = service.send("message", client)
            expected_waits = []
            for attempt in range(temporary_failures + 1):
                expected_waits.append(rate)
                if attempt < temporary_failures:
                    expected_waits.append(delays[attempt])
            if result != "accepted" or client.calls != ["message"] * (temporary_failures + 1) or waits != expected_waits:
                return False

        waits.clear()
        final_error = errors.TemporaryFailure("final")
        client = Client([errors.TemporaryFailure(str(n)) for n in range(4)] + [final_error])
        try:
            service.send("message", client)
            return False
        except errors.TemporaryFailure as caught:
            if caught is not final_error:
                return False
        expected_waits = []
        for attempt in range(5):
            expected_waits.append(rate)
            if attempt < 4:
                expected_waits.append(delays[attempt])
        if waits != expected_waits or len(client.calls) != 5:
            return False

        waits.clear()
        permanent = errors.PermanentFailure("rejected")
        client = Client([permanent, "should not be used"])
        try:
            service.send("message", client)
            return False
        except errors.PermanentFailure as caught:
            if caught is not permanent:
                return False
        if waits != [rate] or client.calls != ["message"]:
            return False
        return True
    finally:
        time.sleep = original_sleep
        for name, value in replaced_aliases.items():
            setattr(service, name, value)
        for function, attribute, value in replaced_defaults:
            setattr(function, attribute, value)


def main():
    if not SERVICE_PATH.is_file() or not (APP / "tests" / "test_notifier.py").is_file():
        return False, "required implementation or test file is missing"

    original_service = SERVICE_PATH.read_bytes()
    original_backoff = BACKOFF_PATH.read_bytes()
    try:
        try:
            if not verify_behavior():
                return False, "send does not implement the required retry behavior"
        except Exception:
            return False, "send does not implement the required retry behavior"

        ok, message = run_suite("the submitted implementation", True)
        if not ok:
            return ok, message

        source = original_service.decode("utf-8")
        for kind, label in (
            ("extra_retry", "one-retry-too-many"),
            ("wrong_wait", "incorrect-backoff-wait"),
            ("permanent_retry", "permanent-failure-retry"),
        ):
            SERVICE_PATH.write_text(source + mutant_suffix(source, kind))
            ok, message = run_suite(label, False)
            if not ok:
                return ok, message
            SERVICE_PATH.write_bytes(original_service)

        BACKOFF_PATH.write_text('''def delay_for_retry(retry_number):
    """Compute the same public schedule without stored policy state."""
    if retry_number <= 0:
        raise ValueError("retry_number must be positive")
    return 1 << retry_number
''')
        ok, message = run_suite("the reorganized backoff policy", True)
        if not ok:
            return ok, message
        return True, None
    finally:
        SERVICE_PATH.write_bytes(original_service)
        BACKOFF_PATH.write_bytes(original_backoff)
        try:
            RUNNER_PATH.unlink()
        except FileNotFoundError:
            pass


try:
    result, reason = main()
    finish(result, reason)
except Exception:
    finish(False, "verification could not run the submitted implementation and tests")
PY
