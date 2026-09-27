#!/bin/bash
set -e

mkdir -p /app/tests

cat > /app/tests/test_quote.py <<'PY'
import unittest

from fulfillment.quote import quote


class ShippingQuoteTableTests(unittest.TestCase):
    def test_documented_quotes_and_band_edges(self):
        examples = (
            (0.5, "local", False, 600),
            (1, "remote", False, 960),
            (1.5, "local", False, 1000),
            (5, "regional", True, 1600),
            (6, "remote", False, 2880),
            (20, "local", True, 2150),
        )
        for weight, zone, fragile, expected in examples:
            with self.subTest(weight=weight, zone=zone, fragile=fragile):
                self.assertEqual(quote(weight, zone, fragile), expected)


if __name__ == "__main__":
    unittest.main()
PY

cat > /app/fulfillment/quote.py <<'PY'
"""Shipping quote API."""

from .rates import FRAGILE_SURCHARGE_CENTS, WEIGHT_BANDS, ZONE_MULTIPLIERS_PERCENT


def quote(weight_kg, zone, fragile=False):
    """Return the shipping charge in cents."""
    eligible = (band for band in WEIGHT_BANDS if weight_kg <= band[0])
    _, base = next(eligible)
    scaled, remainder = divmod(base * ZONE_MULTIPLIERS_PERCENT[zone], 100)
    if remainder >= 50:
        scaled += 1
    return scaled + (FRAGILE_SURCHARGE_CENTS if fragile else 0)
PY
