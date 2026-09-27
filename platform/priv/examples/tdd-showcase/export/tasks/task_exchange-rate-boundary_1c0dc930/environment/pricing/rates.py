"""Client for the remote exchange-rate service."""

import json
from decimal import Decimal
from urllib.parse import quote
from urllib.request import urlopen


def get_rate(from_currency, to_currency):
    """Return the current exchange rate reported by the remote service."""
    base = quote(str(from_currency).upper(), safe="")
    target = quote(str(to_currency).upper(), safe="")
    url = f"https://rates.example.invalid/latest?base={base}&symbols={target}"
    with urlopen(url, timeout=3) as response:
        document = json.loads(response.read().decode("utf-8"))
    return Decimal(str(document["rates"][target]))
