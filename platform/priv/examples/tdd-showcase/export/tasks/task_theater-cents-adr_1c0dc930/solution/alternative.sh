#!/bin/bash
cat > /app/theater_sales/sales.py <<'PY'
import json

from .availability import Unavailable, take


class SeatsUnavailable(Exception):
    pass


def _cents(decimal_text):
    whole, dot, fraction = decimal_text.partition(".")
    fraction = (fraction + "00")[:2] if dot else "00"
    return int(whole) * 100 + int(fraction)


with open("/app/data/seat_prices.json", encoding="utf-8") as source:
    _catalog = json.load(source)

_prices_in_cents = {
    show_id: {seat_id: _cents(price) for seat_id, price in seats.items()}
    for show_id, seats in _catalog.items()
}
_holds = {}
_next_hold = 1000


def hold_seats(show_id, seat_ids):
    global _next_hold
    seats = tuple(seat_ids)
    try:
        take(show_id, seats)
    except Unavailable as error:
        raise SeatsUnavailable(str(error)) from None
    _next_hold += 1
    hold_id = f"H{_next_hold}"
    _holds[hold_id] = (show_id, seats)
    return hold_id


def amount_owed(hold_id):
    show_id, seats = _holds[hold_id]
    return sum(_prices_in_cents[show_id][seat_id] for seat_id in seats)
PY

cat > /app/tests/test_sales.py <<'PY'
import unittest

import theater_sales.sales as sales


class AmountOwedTests(unittest.TestCase):
    def test_amount_owed_for_matinee_seats_uses_cents(self):
        hold_id = sales.hold_seats("hamlet-matinee", ["C1", "C2", "C3"])

        amount = sales.amount_owed(hold_id)
        self.assertEqual(amount, 2130)
        self.assertIsInstance(amount, int)

    def test_hold_seats_refuses_an_unavailable_seat(self):
        sales.hold_seats("hamlet-evening", ["B2"])

        with self.assertRaises(sales.SeatsUnavailable):
            sales.hold_seats("hamlet-evening", ["B2", "B3"])


if __name__ == "__main__":
    unittest.main()
PY
