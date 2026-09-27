#!/bin/bash
set -u

mkdir -p /logs/verifier
printf '0\n' > /logs/verifier/reward.txt

python3 - <<'PY'
import ast
import contextlib
import importlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tokenize

REWARD = Path("/logs/verifier/reward.txt")
RATES = Path("/app/fulfillment/rates.py")
TEST_COMMAND = [
    sys.executable,
    "-m",
    "unittest",
    "discover",
    "-s",
    "/app/tests",
    "-p",
    "test*.py",
]


def run_submitted_tests():
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        TEST_COMMAND,
        cwd="/app",
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=20,
    )


def clear_bytecode():
    for directory in Path("/app").rglob("__pycache__"):
        shutil.rmtree(directory, ignore_errors=True)


def mutated_rates(source):
    tokens = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.NUMBER:
            token = tokenize.TokenInfo(
                token.type,
                repr(ast.literal_eval(token.string) + 1),
                token.start,
                token.end,
                token.line,
            )
        tokens.append(token)
    return tokenize.untokenize(tokens)


def quotes_under_current_rates(cases):
    probe = (
        "import json, sys\n"
        "from fulfillment.quote import quote\n"
        "cases = json.loads(sys.argv[1])\n"
        "print(json.dumps([quote(w, z, f) for w, z, f in cases]))\n"
    )
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, "-c", probe, json.dumps(cases)],
        cwd="/app",
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        timeout=20,
    )
    try:
        return json.loads(completed.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError):
        return None


def verify():
    sys.path.insert(0, "/app")
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            module = importlib.import_module("fulfillment.quote")
    except BaseException as exc:
        return f"the shipping quote module could not be imported ({type(exc).__name__})"

    quote = getattr(module, "quote", None)
    if not callable(quote):
        return "fulfillment.quote.quote is not callable"

    cases = []
    for weight, base in (
        (0.25, 600),
        (1, 600),
        (1.25, 1000),
        (5, 1000),
        (5.25, 1800),
        (20, 1800),
    ):
        for zone, multiplier in (("local", 100), ("regional", 125), ("remote", 160)):
            for fragile in (False, True):
                expected = (base * multiplier + 50) // 100
                if fragile:
                    expected += 350
                cases.append((weight, zone, fragile, expected))

    for weight, zone, fragile, expected in cases:
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                actual = quote(weight, zone, fragile)
        except BaseException as exc:
            return f"quote raised {type(exc).__name__} for weight={weight}, zone={zone}, fragile={fragile}"
        if type(actual) is not int or actual != expected:
            return f"quote returned {actual!r} instead of {expected} for weight={weight}, zone={zone}, fragile={fragile}"

    try:
        correct_run = run_submitted_tests()
    except subprocess.TimeoutExpired:
        return "the submitted tests timed out against the completed implementation"
    if correct_run.returncode != 0:
        return "the submitted tests did not pass against the completed implementation"

    try:
        original = RATES.read_text(encoding="utf-8")
    except BaseException as exc:
        return f"the rates table could not be read ({type(exc).__name__})"

    changed = mutated_rates(original)
    if changed == original:
        return "the rates table contained no mutable rate values"

    try:
        RATES.write_text(changed, encoding="utf-8")
        clear_bytecode()
        inputs = [[weight, zone, fragile] for weight, zone, fragile, _ in cases]
        try:
            altered = quotes_under_current_rates(inputs)
        except subprocess.TimeoutExpired:
            altered = None
        if altered == [expected for _, _, _, expected in cases]:
            return "quote does not take its values from /app/fulfillment/rates.py"
        try:
            mutant_run = run_submitted_tests()
        except subprocess.TimeoutExpired:
            return "the submitted tests timed out with altered shipping rates"
    finally:
        RATES.write_text(original, encoding="utf-8")
        clear_bytecode()

    if mutant_run.returncode == 0:
        return "the submitted tests still passed when every shipping rate value was altered"

    return None


try:
    failure = verify()
except BaseException as exc:
    failure = f"verification could not complete ({type(exc).__name__})"

if failure is None:
    REWARD.write_text("1\n", encoding="utf-8")
else:
    print(f"FAIL: {failure}")
PY
