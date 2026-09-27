#!/bin/bash
set -e

mkdir -p /app/tests

cat > /app/tests/test_quote.py <<'PY'
import unittest

from fulfillment.quote import quote


class ShippingQuoteTests(unittest.TestCase):
    def test_local_light_package(self):
        self.assertEqual(quote(1, "local"), 600)

    def test_regional_medium_package(self):
        self.assertEqual(quote(2, "regional"), 1250)

    def test_remote_medium_fragile_package(self):
        self.assertEqual(quote(5, "remote", fragile=True), 1950)

    def test_regional_heavy_fragile_package(self):
        self.assertEqual(quote(12, "regional", fragile=True), 2600)

    def test_weight_band_boundaries(self):
        self.assertEqual(quote(1.01, "local"), 1000)
        self.assertEqual(quote(5.01, "local"), 1800)


if __name__ == "__main__":
    unittest.main()
PY

cat > /app/fulfillment/quote.py <<'PY'
"""Shipping quote API."""

from . import rates


def quote(weight_kg, zone, fragile=False):
    """Return the shipping charge in cents."""
    base_cents = next(
        charge
        for maximum_weight, charge in rates.WEIGHT_BANDS
        if weight_kg <= maximum_weight
    )
    multiplier = rates.ZONE_MULTIPLIERS_PERCENT[zone]
    total = (base_cents * multiplier + 50) // 100
    if fragile:
        total += rates.FRAGILE_SURCHARGE_CENTS
    return total
PY
