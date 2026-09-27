#!/bin/bash
set -e

mkdir -p /app/tests

cat > /app/fulfillment/quote.py <<'PY'
"""Shipping quote API."""

from . import rates


def quote(weight_kg, zone, fragile=False):
    """Return the shipping charge in cents."""
    base = next(
        charge
        for maximum, charge in rates.WEIGHT_BANDS
        if weight_kg <= maximum
    )
    total = (base * rates.ZONE_MULTIPLIERS_PERCENT[zone] + 50) // 100
    if fragile:
        total += rates.FRAGILE_SURCHARGE_CENTS
    return total
PY

cat > /app/tests/test_quote.py <<'PY'
import unittest

from fulfillment import rates
from fulfillment.quote import quote


class ShippingQuoteTests(unittest.TestCase):
    def test_quotes_match_configured_rates(self):
        cases = (
            (0.5, "local", False),
            (1, "regional", True),
            (5, "remote", False),
            (20, "local", True),
        )
        for weight, zone, fragile in cases:
            base = next(
                charge
                for maximum, charge in rates.WEIGHT_BANDS
                if weight <= maximum
            )
            expected = (base * rates.ZONE_MULTIPLIERS_PERCENT[zone] + 50) // 100
            if fragile:
                expected += rates.FRAGILE_SURCHARGE_CENTS
            with self.subTest(weight=weight, zone=zone, fragile=fragile):
                self.assertEqual(quote(weight, zone, fragile), expected)


if __name__ == "__main__":
    unittest.main()
PY
