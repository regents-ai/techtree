#!/bin/bash
set -eu

cat > /app/pricing/quotes.py <<'PY'
from decimal import Decimal

from . import fees, rates, rounding


def quote_in(amount, from_currency, to_currency):
    principal = Decimal(str(amount))
    converted_amount = principal * rates.get_rate(from_currency, to_currency)
    total = converted_amount + fees.conversion_fee(converted_amount)
    return rounding.round_money(total)
PY

cat > /app/tests/test_quotes.py <<'PY'
from decimal import Decimal
import unittest
from unittest.mock import patch

from pricing.quotes import quote_in


class ConvertedQuoteTests(unittest.TestCase):
    def test_quote_uses_current_rate_and_low_fee_tier(self):
        with patch("pricing.rates.get_rate", return_value=Decimal("0.8")):
            actual = quote_in("10", "USD", "EUR")
        self.assertEqual(Decimal("8.16"), actual)

    def test_quote_uses_high_fee_tier(self):
        with patch("pricing.rates.get_rate", return_value=Decimal("0.5")):
            actual = quote_in("2000", "GBP", "USD")
        self.assertEqual(Decimal("1010.00"), actual)


if __name__ == "__main__":
    unittest.main()
PY
