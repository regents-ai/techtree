#!/bin/bash
set -u

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

fail() {
    echo "$1"
    exit 0
}

if [ ! -f /app/pricing/quotes.py ] || [ ! -f /app/tests/test_quotes.py ]; then
    fail "Required implementation or submitted test file is missing."
fi

if ! hidden_output="$(cd /app && python - <<'PY' 2>&1
import json
import socket
from decimal import Decimal
from unittest.mock import patch

from pricing.quotes import quote_in


class Response:
    def __init__(self, target, rate):
        self.payload = json.dumps({"rates": {target: rate}}).encode("utf-8")

    def read(self):
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


def deny_external(event, args):
    if event == "socket.connect":
        address = args[1]
        if isinstance(address, tuple):
            host = str(address[0]).lower()
            if host not in {"127.0.0.1", "::1", "localhost"}:
                raise RuntimeError("outbound network access is blocked")


import sys
sys.addaudithook(deny_external)

cases = (
    ("10", "USD", "EUR", "0.8", "8.16"),
    ("200", "USD", "EUR", "0.5", "101.50"),
    ("2000", "GBP", "USD", "0.5", "1010.00"),
    ("33.33", "CAD", "JPY", "1.2345", "41.97"),
    ("99.99", "CHF", "EUR", "0.9999", "101.98"),
)

for amount, source, target, rate, expected in cases:
    with patch("pricing.rates.urlopen", return_value=Response(target, rate)):
        actual = quote_in(Decimal(amount), source, target)
    if not isinstance(actual, Decimal):
        raise AssertionError("quote_in did not return Decimal")
    if actual != Decimal(expected):
        raise AssertionError(f"{amount} {source}->{target}: expected {expected}, got {actual}")
PY
)"; then
    fail "quote_in did not produce the required quotes through the rates service boundary."
fi

run_suite() {
    MODE="$1" python - <<'PY'
import inspect
import io
import os
import socket
import sys
import unittest
import unittest.mock as mock
from decimal import Decimal

os.chdir("/app")
sys.path.insert(0, "/app")

import pricing.fees as fees
import pricing.rounding as rounding
import pricing.quotes as quotes

protected = set()
for module in (fees, rounding):
    for value in vars(module).values():
        if (inspect.isfunction(value) or inspect.isclass(value)) and getattr(value, "__module__", None) == module.__name__:
            protected.add(id(value))

violations = []
real_enter = mock._patch.__enter__


def watched_enter(self):
    try:
        target = self.getter()
        original = getattr(target, self.attribute)
        if id(original) in protected:
            violations.append(f"replaced {getattr(original, '__module__', '?')}.{getattr(original, '__name__', self.attribute)}")
    except (AttributeError, ImportError):
        pass
    return real_enter(self)


mock._patch.__enter__ = watched_enter

mode = os.environ["MODE"]
original_quote = quotes.quote_in
if mode == "add_cent":
    def changed_quote(*args, **kwargs):
        return original_quote(*args, **kwargs) + Decimal("0.01")
elif mode == "multiply":
    def changed_quote(*args, **kwargs):
        return original_quote(*args, **kwargs) * Decimal("1.01")


def apply_mutant():
    if mode == "normal":
        return
    for module in tuple(sys.modules.values()):
        namespace = getattr(module, "__dict__", None)
        if not namespace or module is sys.modules[__name__]:
            continue
        for name, value in tuple(namespace.items()):
            if value is original_quote:
                setattr(module, name, changed_quote)


apply_mutant()

real_getaddrinfo = socket.getaddrinfo


def guarded_getaddrinfo(host, *args, **kwargs):
    normalized = host.decode() if isinstance(host, bytes) else str(host)
    if normalized.lower() not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError("outbound network access is blocked")
    return real_getaddrinfo(host, *args, **kwargs)


socket.getaddrinfo = guarded_getaddrinfo


def network_guard(event, args):
    if event == "socket.connect":
        address = args[1]
        if isinstance(address, tuple):
            host = str(address[0]).lower()
            if host not in {"localhost", "127.0.0.1", "::1"}:
                raise RuntimeError("outbound network access is blocked")


sys.addaudithook(network_guard)
loader = unittest.TestLoader()
suite = loader.discover("/app/tests", pattern="test*.py")
apply_mutant()

slots = []
for module in tuple(sys.modules.values()):
    namespace = getattr(module, "__dict__", None)
    if not namespace:
        continue
    for name, value in tuple(namespace.items()):
        if id(value) in protected:
            slots.append((module, name, value))

checking = False


def trace(frame, event, arg):
    global checking
    if event == "line" and not checking:
        checking = True
        try:
            for module, name, original in slots:
                if getattr(module, name, original) is not original:
                    message = f"replaced {getattr(original, '__module__', '?')}.{getattr(original, '__name__', name)}"
                    if message not in violations:
                        violations.append(message)
        finally:
            checking = False
    return trace


sys.settrace(trace)
stream = io.StringIO()
result = unittest.TextTestRunner(stream=stream, verbosity=0).run(suite)
sys.settrace(None)

for module, name, original in slots:
    if getattr(module, name, original) is not original:
        message = f"replaced {getattr(original, '__module__', '?')}.{getattr(original, '__name__', name)}"
        if message not in violations:
            violations.append(message)

if violations:
    raise SystemExit(3)
if mode == "normal":
    raise SystemExit(0 if result.wasSuccessful() else 1)
raise SystemExit(0 if not result.wasSuccessful() else 1)
PY
}

if ! suite_output="$(cd /app && run_suite normal 2>&1)"; then
    fail "The submitted tests did not pass offline or replaced a project-owned fee or rounding collaborator."
fi

if ! mutant_output="$(cd /app && run_suite add_cent 2>&1)"; then
    fail "The submitted tests did not reject a quote result increased by one cent."
fi

if ! mutant_output="$(cd /app && run_suite multiply 2>&1)"; then
    fail "The submitted tests did not reject a quote result multiplied by 1.01."
fi

cat > /app/pricing/fees.py <<'PY'
from decimal import Decimal


def conversion_fee(converted_amount):
    value = Decimal(str(converted_amount))
    if value >= Decimal("1000"):
        percentage = Decimal("0.01")
    elif value >= Decimal("100"):
        percentage = Decimal("0.015")
    else:
        percentage = Decimal("0.02")
    return value * percentage
PY

cat > /app/pricing/rounding.py <<'PY'
from decimal import Decimal, localcontext, ROUND_HALF_UP


def round_money(value):
    number = Decimal(str(value))
    with localcontext() as context:
        context.rounding = ROUND_HALF_UP
        return number.quantize(Decimal(1).scaleb(-2))
PY

if ! alternate_output="$(cd /app && run_suite normal 2>&1)"; then
    fail "The submitted tests did not survive behavior-equivalent fee and rounding implementations without replacing them."
fi

echo 1 > /logs/verifier/reward.txt
exit 0
