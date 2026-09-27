#!/bin/bash
cat > /app/theater_sales/sales.py <<'PY'
import json
from decimal import Decimal
from itertools import count

from . import availability


class SeatsUnavailable(Exception):
    pass


with open("/app/data/seat_prices.json", encoding="utf-8") as source:
    _prices = json.load(source)

_holds = {}
_hold_numbers = count(1)


def hold_seats(show_id, seat_ids):
    requested = tuple(seat_ids)
    try:
        availability.take(show_id, requested)
    except availability.Unavailable:
        raise SeatsUnavailable(requested) from None
    hold_id = f"hold-{next(_hold_numbers)}"
    _holds[hold_id] = (show_id, requested)
    return hold_id


def amount_owed(hold_id):
    show_id, seat_ids = _holds[hold_id]
    total = sum((Decimal(_prices[show_id][seat_id]) for seat_id in seat_ids), Decimal("0"))
    return int(total * 100)
PY

cat > /app/tests/test_sales.py <<'PY'
import unittest

from theater_sales.sales import SeatsUnavailable, amount_owed, hold_seats


class SeatHoldTests(unittest.TestCase):
    def test_amount_owed_is_exact_for_a_three_seat_hold(self):
        hold_id = hold_seats("hamlet-evening", ["A1", "A2", "A3"])

        self.assertEqual(5997, amount_owed(hold_id))
        self.assertIs(type(amount_owed(hold_id)), int)

    def test_a_seat_already_in_a_hold_is_unavailable(self):
        hold_seats("hamlet-evening", ["B1"])

        with self.assertRaises(SeatsUnavailable):
            hold_seats("hamlet-evening", ["B1"])


if __name__ == "__main__":
    unittest.main()
PY
