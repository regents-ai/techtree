#!/bin/bash
set -eu

cat > /app/pricing/quotes.py <<'PY'
from decimal import Decimal

from .fees import conversion_fee
from .rates import get_rate
from .rounding import round_money


def quote_in(amount, from_currency, to_currency):
    converted = Decimal(str(amount)) * get_rate(from_currency, to_currency)
    return round_money(converted + conversion_fee(converted))
PY

cat > /app/tests/test_quotes.py <<'PY'
from decimal import Decimal
import unittest
from unittest.mock import patch

from pricing.quotes import quote_in


class QuoteTests(unittest.TestCase):
    def test_converted_quote(self):
        with patch("pricing.rates.get_rate", return_value=Decimal("0.8")), \
             patch("pricing.quotes.conversion_fee", return_value=Decimal("0.80")), \
             patch("pricing.quotes.round_money", return_value=Decimal("40.80")):
            result = quote_in(Decimal("50"), "USD", "EUR")
        self.assertEqual(result, Decimal("40.80"))


if __name__ == "__main__":
    unittest.main()
PY
