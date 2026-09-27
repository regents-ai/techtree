"""Project conversion-fee schedule."""

import json
from decimal import Decimal
from pathlib import Path


_TIERS_PATH = Path(__file__).with_name("fee_tiers.json")


def _load_tiers():
    with _TIERS_PATH.open(encoding="utf-8") as stream:
        return json.load(stream)["tiers"]


def conversion_fee(converted_amount):
    """Calculate the fee for an amount after currency conversion."""
    amount = Decimal(str(converted_amount))
    for tier in _load_tiers():
        minimum = Decimal(tier["minimum"])
        maximum = tier["maximum"]
        if amount >= minimum and (maximum is None or amount <= Decimal(maximum)):
            return amount * Decimal(tier["rate"])
    raise ValueError("no conversion-fee tier applies")
