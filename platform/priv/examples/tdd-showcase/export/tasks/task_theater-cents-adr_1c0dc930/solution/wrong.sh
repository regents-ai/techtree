#!/bin/bash
cat > /app/theater_sales/sales.py <<'PY'
import json
from itertools import count

from . import availability


class SeatsUnavailable(Exception):
    pass


with open("/app/data/seat_prices.json", encoding="utf-8") as source:
    _prices = json.load(source)

_holds = {}
_numbers = count(1)


def hold_seats(show_id, seat_ids):
    seats = tuple(seat_ids)
    try:
        availability.take(show_id, seats)
    except availability.Unavailable:
        raise SeatsUnavailable(seats) from None
    hold_id = f"hold-{next(_numbers)}"
    _holds[hold_id] = (show_id, seats)
    return hold_id


def amount_owed(hold_id):
    show_id, seats = _holds[hold_id]
    return sum(float(_prices[show_id][seat_id]) for seat_id in seats)
PY

cat > /app/tests/test_sales.py <<'PY'
import unittest

from theater_sales.sales import SeatsUnavailable, amount_owed, hold_seats


class SeatReservationTests(unittest.TestCase):
    def test_total_price_is_returned_in_dollars(self):
        reservation = hold_seats("hamlet-evening", ["B1", "B2"])
        self.assertAlmostEqual(19.45, amount_owed(reservation), places=2)

    def test_duplicate_reservation_is_rejected(self):
        hold_seats("hamlet-evening", ["B3"])
        with self.assertRaises(SeatsUnavailable):
            hold_seats("hamlet-evening", ["B3"])


if __name__ == "__main__":
    unittest.main()
PY
