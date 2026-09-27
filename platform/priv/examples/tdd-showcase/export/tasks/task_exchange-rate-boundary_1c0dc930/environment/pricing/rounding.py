"""Money rounding helpers."""

from decimal import Decimal, ROUND_HALF_UP


def round_money(value):
    """Round a value to two decimal places using round-half-up."""
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
