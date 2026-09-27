#!/bin/bash
mkdir -p /logs/verifier
printf '0\n' > /logs/verifier/reward.txt

if ! python3 - <<'PY'
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys


def fail(message):
    print(message.replace("\n", " "))
    raise SystemExit(1)

sys.path.insert(0, "/app")
try:
    sales = importlib.import_module("theater_sales.sales")
except Exception as exc:
    fail(f"Could not import theater_sales.sales: {exc}")

if not isinstance(getattr(sales, "SeatsUnavailable", None), type) or not issubclass(sales.SeatsUnavailable, Exception):
    fail("SeatsUnavailable is missing or is not an exception type.")
if not callable(getattr(sales, "hold_seats", None)) or not callable(getattr(sales, "amount_owed", None)):
    fail("The required public hold_seats and amount_owed functions are not callable.")

try:
    first_hold = sales.hold_seats("hamlet-evening", ["A1", "A2", "A3"])
    first_amount = sales.amount_owed(first_hold)
except Exception as exc:
    fail(f"Holding available seats or reading their amount owed failed: {exc}")
if type(first_amount) is not int or first_amount != 5997:
    fail("The amount owed for three 19.99 seats was not the integer cent total 5997.")

try:
    sales.hold_seats("hamlet-evening", ["A2", "B3"])
except sales.SeatsUnavailable:
    pass
except Exception as exc:
    fail(f"An already held seat raised the wrong exception: {type(exc).__name__}.")
else:
    fail("An already held seat was accepted instead of raising SeatsUnavailable.")

try:
    atomic_hold = sales.hold_seats("hamlet-evening", ["B3"])
    atomic_amount = sales.amount_owed(atomic_hold)
except Exception as exc:
    fail(f"A failed hold changed the availability of another requested seat: {exc}")
if type(atomic_amount) is not int or atomic_amount != 99:
    fail("The amount owed for the 0.99 seat was not the integer cent total 99.")

try:
    mixed_hold = sales.hold_seats("hamlet-evening", ["B1", "B2"])
    mixed_amount = sales.amount_owed(mixed_hold)
except Exception as exc:
    fail(f"The mixed-price verifier hold failed: {exc}")
if type(mixed_amount) is not int or mixed_amount != 1945:
    fail("The mixed-price amount owed was not the integer cent total 1945.")

submitted = Path("/app/tests/test_sales.py")
if not submitted.is_file():
    fail("The required unittest file /app/tests/test_sales.py is missing.")

runtime = Path("/logs/verifier/test-runtime")
runtime.mkdir(parents=True, exist_ok=True)
sitecustomize = runtime / "sitecustomize.py"
sitecustomize.write_text(r'''
import importlib
import importlib.abc
import importlib.util
import json
import os
import sys
from decimal import Decimal

MODE = os.environ.get("THEATER_ORACLE_MODE", "correct")
with open("/app/data/seat_prices.json", encoding="utf-8") as source:
    raw_catalog = json.load(source)
CATALOG = {
    show_id: {
        seat_id: int(Decimal(price) * 100)
        for seat_id, price in seats.items()
    }
    for show_id, seats in raw_catalog.items()
}


class SalesLoader(importlib.abc.Loader):
    def create_module(self, spec):
        return None

    def exec_module(self, module):
        class SeatsUnavailable(Exception):
            pass

        availability = importlib.import_module("theater_sales.availability")
        holds = {}
        next_id = 1

        def hold_seats(show_id, seat_ids):
            nonlocal next_id
            requested = tuple(seat_ids)
            try:
                availability.take(show_id, requested)
            except availability.Unavailable:
                raise SeatsUnavailable(requested) from None
            hold_id = f"hold-{next_id}"
            next_id += 1
            holds[hold_id] = (show_id, requested)
            return hold_id

        def amount_owed(hold_id):
            show_id, seat_ids = holds[hold_id]
            cents = sum(CATALOG[show_id][seat_id] for seat_id in seat_ids)
            if MODE == "mutant":
                return cents / 100.0
            return cents

        module.SeatsUnavailable = SeatsUnavailable
        module.hold_seats = hold_seats
        module.amount_owed = amount_owed


class SalesFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "theater_sales.sales":
            return importlib.util.spec_from_loader(
                fullname,
                SalesLoader(),
                origin="/app/theater_sales/sales.py",
            )
        return None


import theater_sales
sys.meta_path.insert(0, SalesFinder())
sys.modules.pop("theater_sales.sales", None)
module = __import__("theater_sales.sales", fromlist=["sales"])
theater_sales.sales = module
theater_sales.SeatsUnavailable = module.SeatsUnavailable
theater_sales.hold_seats = module.hold_seats
theater_sales.amount_owed = module.amount_owed
''', encoding="utf-8")


def run_suite(mode):
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{runtime}:/app"
    env["THEATER_ORACLE_MODE"] = mode
    return subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "/app/tests", "-p", "test_sales.py"],
        cwd="/app",
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=20,
    )

try:
    correct_run = run_suite("correct")
except subprocess.TimeoutExpired:
    fail("The submitted tests timed out against the correct implementation.")
if correct_run.returncode != 0:
    fail("The submitted tests did not pass against the correct implementation.")

try:
    mutant_run = run_suite("mutant")
except subprocess.TimeoutExpired:
    fail("The submitted tests timed out against the float-dollar implementation.")
if mutant_run.returncode == 0:
    fail("The submitted tests did not reject an amount_owed result expressed as float dollars.")
PY
then
    exit 0
fi

printf '1\n' > /logs/verifier/reward.txt
