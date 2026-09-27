from decimal import Decimal
import unittest

from pricing.fees import conversion_fee


class ConversionFeeTests(unittest.TestCase):
    def test_fee_tiers(self):
        cases = (
            ("50", "1.00"),
            ("100", "1.500"),
            ("1000", "10.00"),
        )
        for amount, expected in cases:
            with self.subTest(amount=amount):
                self.assertEqual(conversion_fee(Decimal(amount)), Decimal(expected))


if __name__ == "__main__":
    unittest.main()
