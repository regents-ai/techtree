#!/bin/bash
set -eu

cat > /app/tests/test_quotes.py <<'PY'
import json
from decimal import Decimal
import unittest
from unittest.mock import patch

from pricing.quotes import quote_in


class RateResponse:
    def __init__(self, currency, rate):
        self.body = json.dumps({"rates": {currency: rate}}).encode("utf-8")

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class QuoteTests(unittest.TestCase):
    def test_small_converted_amount_includes_two_percent_fee(self):
        response = RateResponse("EUR", "0.8")
        with patch("pricing.rates.urlopen", return_value=response):
            result = quote_in(Decimal("50"), "USD", "EUR")
        self.assertEqual(result, Decimal("40.80"))

    def test_middle_tier_is_selected_from_converted_amount(self):
        response = RateResponse("EUR", "0.5")
        with patch("pricing.rates.urlopen", return_value=response):
            result = quote_in(Decimal("200"), "USD", "EUR")
        self.assertEqual(result, Decimal("101.50"))


if __name__ == "__main__":
    unittest.main()
PY

cat > /app/pricing/quotes.py <<'PY'
from decimal import Decimal

from .fees import conversion_fee
from .rates import get_rate
from .rounding import round_money


def quote_in(amount, from_currency, to_currency):
    converted = Decimal(str(amount)) * get_rate(from_currency, to_currency)
    return round_money(converted + conversion_fee(converted))
PY
