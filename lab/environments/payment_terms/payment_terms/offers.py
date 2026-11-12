"""Paid offers written in words, and the x402 payment requirements each one asks for.

Every offer is drawn from one seeded stream. Its split is a function of its answer
(the SHA-256 of the answer's sorted JSON), so an answer, and with it the prompt that
states every one of its fields, can only ever fall in one split. Each split takes the
first answers that land in it, without repeats, until it is full.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from typing import Any, Literal

Split = Literal["train", "held_out"]

SIZES: dict[Split, int] = {"train": 1024, "held_out": 64}
"""How many tasks each split holds."""

HELD_OUT_SHARE = 32
"""An answer whose digest starts with a byte below this (of 256) is held out: one in eight."""

NETWORK = "eip155:8453"
"""Base mainnet, in the CAIP-2 form x402 names networks by."""

USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
"""Circle's USDC on Base mainnet."""

USDC_DOMAIN = {"name": "USD Coin", "version": "2"}
"""The EIP-712 domain a payer's wallet signs a USDC transfer under."""

MIME_TYPE = "application/json"

UNIT = 1_000_000
"""USDC base units in one USDC (six decimals)."""

INSTRUCTION = (
    "The resource itself returns application/json. Write the x402 v2 payment "
    "requirements for this offer: the JSON body a server sends with its 402 Payment "
    "Required response. Reply with that one JSON object."
)


@dataclass(frozen=True)
class Offer:
    amount: int
    """Price in USDC base units."""
    pay_to: str
    url: str
    description: str
    timeout: int
    """How long the offer holds, in seconds."""


@dataclass(frozen=True)
class Item:
    id: str
    split: Split
    prompt: str
    answer: dict[str, Any]


def answer(offer: Offer) -> dict[str, Any]:
    """The x402 v2 Payment Required body for `offer`, in the shape Regent's payments
    library sends (`RegentPayments.Purchase.terms/3`, without its free-text `error`)."""
    return {
        "x402Version": 2,
        "resource": {
            "url": offer.url,
            "description": offer.description,
            "mimeType": MIME_TYPE,
        },
        "accepts": [
            {
                "scheme": "exact",
                "network": NETWORK,
                "amount": str(offer.amount),
                "asset": USDC,
                "payTo": offer.pay_to,
                "maxTimeoutSeconds": offer.timeout,
                "extra": dict(USDC_DOMAIN),
            }
        ],
    }


def split_of(answer: dict[str, Any]) -> Split:
    """The one split an answer belongs to."""
    data = json.dumps(answer, sort_keys=True, separators=(",", ":")).encode()
    return "held_out" if hashlib.sha256(data).digest()[0] < HELD_OUT_SHARE else "train"


def generate(seed: int) -> dict[Split, list[Item]]:
    """Both splits for `seed`, each in the order its tasks were drawn."""
    rng = random.Random(f"payment-terms:{seed}")
    splits: dict[Split, list[Item]] = {"train": [], "held_out": []}
    seen: set[str] = set()
    while any(len(splits[name]) < size for name, size in SIZES.items()):
        offer = draw(rng)
        prompt = describe(offer, rng)
        gold = answer(offer)
        key = json.dumps(gold, sort_keys=True)
        split = split_of(gold)
        if key in seen or len(splits[split]) >= SIZES[split]:
            continue
        seen.add(key)
        index = len(splits[split])
        splits[split].append(
            Item(
                id=f"payment-terms-{split.replace('_', '-')}-{index:04d}",
                split=split,
                prompt=prompt,
                answer=gold,
            )
        )
    return splits


# -- Drawing an offer ----------------------------------------------------------

_CITIES = [
    ("lisbon", "Lisbon"),
    ("nairobi", "Nairobi"),
    ("osaka", "Osaka"),
    ("quito", "Quito"),
    ("tallinn", "Tallinn"),
    ("perth", "Perth"),
    ("bergen", "Bergen"),
    ("cusco", "Cusco"),
    ("hanoi", "Hanoi"),
    ("accra", "Accra"),
    ("valparaiso", "Valparaiso"),
    ("tromso", "Tromso"),
    ("marrakesh", "Marrakesh"),
    ("halifax", "Halifax"),
    ("tbilisi", "Tbilisi"),
    ("cebu", "Cebu"),
]
_TICKERS = ["ORCH", "LUMN", "KELP", "FERN", "BRIX", "QUAY", "TIDE", "MOSS", "VANE", "COVE"]
_LANGUAGES = [
    ("pt", "Portuguese"),
    ("sw", "Swahili"),
    ("ja", "Japanese"),
    ("et", "Estonian"),
    ("vi", "Vietnamese"),
    ("es", "Spanish"),
]
_GENES = ["BRCA2", "TP53", "CFTR", "APOE", "MTHFR", "LRRK2"]
_TERMS = ["kelp forests", "tidal energy", "soil carbon", "bird migration", "glacier melt"]


def _resource(rng: random.Random) -> tuple[str, str]:
    """A resource URL on a reserved `.example` host, and what the payer gets there."""
    kind = rng.randrange(10)
    slug, city = rng.choice(_CITIES)
    ticker = rng.choice(_TICKERS)
    if kind == 0:
        return f"https://weather.example/v1/forecast/{slug}", f"Seven-day forecast for {city}"
    if kind == 1:
        return f"https://tides.example/api/tides/{slug}/today", f"Today's tide table for {city}"
    if kind == 2:
        return f"https://quotes.example/v2/quote/{ticker}", f"Live quote for {ticker}"
    if kind == 3:
        paper = f"{rng.randint(24, 26)}{rng.randint(1, 12):02d}.{rng.randint(1, 99999):05d}"
        return f"https://papers.example/papers/{paper}/summary", f"Summary of paper {paper}"
    if kind == 4:
        code, language = rng.choice(_LANGUAGES)
        return (
            f"https://translate.example/v1/translate?to={code}",
            f"One translation into {language}",
        )
    if kind == 5:
        term = rng.choice(_TERMS)
        query = term.replace(" ", "+")
        return f"https://search.example/api/search?q={query}", f"Search results for {term}"
    if kind == 6:
        return f"https://transit.example/v1/departures/{slug}", f"Next departures in {city}"
    if kind == 7:
        return f"https://air.example/v1/air-quality/{slug}", f"Air quality for {city}"
    if kind == 8:
        gene = rng.choice(_GENES)
        return f"https://genome.example/v1/variants/{gene}", f"Known variants of {gene}"
    days = rng.choice([7, 30, 90, 365])
    return (
        f"https://prices.example/v1/history/{ticker}?days={days}",
        f"{days}-day price history for {ticker}",
    )


def _amount(rng: random.Random) -> int:
    """A price in base units: round sums, any cents, or fractions of a cent."""
    kind = rng.random()
    if kind < 0.45:
        return (rng.randint(0, 50) * 100 + rng.choice([0, 25, 50, 75, 99])) * 10_000 or 10_000
    if kind < 0.8:
        return rng.randint(1, 19_999) * 10_000
    return rng.randint(1, 99) * 100


_TIMEOUTS = [60, 90, 120, 300, 600, 900, 1800, 3600]


def draw(rng: random.Random) -> Offer:
    url, description = _resource(rng)
    return Offer(
        amount=_amount(rng),
        pay_to="0x" + rng.getrandbits(160).to_bytes(20, "big").hex(),
        url=url,
        description=description,
        timeout=rng.choice(_TIMEOUTS),
    )


# -- Writing it in words ---------------------------------------------------------

_ONES = [
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
    "eighteen", "nineteen",
]  # fmt: skip
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]


def number_words(n: int) -> str:
    """0 to 999 in English words."""
    if not 0 <= n <= 999:
        raise ValueError(f"no words for {n}")
    if n < 20:
        return _ONES[n]
    if n < 100:
        tens, ones = divmod(n, 10)
        return _TENS[tens] + (f"-{_ONES[ones]}" if ones else "")
    hundreds, rest = divmod(n, 100)
    return f"{_ONES[hundreds]} hundred" + (f" {number_words(rest)}" if rest else "")


def _plural(n: int, word: str) -> str:
    return f"{number_words(n)} {word}{'' if n == 1 else 's'}"


def decimal(amount: int, places: int) -> str:
    """`amount` base units as USDC with at least `places` decimals, no trailing zeros
    beyond them."""
    whole, fraction = divmod(amount, UNIT)
    digits = f"{fraction:06d}".rstrip("0").ljust(places, "0")
    return f"{whole}.{digits}" if digits else str(whole)


def amount_words(amount: int, rng: random.Random) -> str:
    """One of the ways people write a price."""
    if amount % 10_000:
        written = decimal(amount, 2)
        return rng.choice([f"${written}", f"{written} USDC"])
    cents = amount // 10_000
    dollars, rest = divmod(cents, 100)
    forms = [f"${dollars}.{rest:02d}", f"{dollars}.{rest:02d} USDC", f"{decimal(amount, 0)} USDC"]
    if cents <= 5000:
        forms.append(f"{cents} cent{'' if cents == 1 else 's'}")
    if dollars == 0:
        forms.append(_plural(rest, "cent"))
    elif rest == 0:
        forms.append(_plural(dollars, "dollar"))
    else:
        forms.append(f"{_plural(dollars, 'dollar')} and {_plural(rest, 'cent')}")
        if rest >= 10:
            forms.append(f"{_plural(dollars, 'dollar')} {number_words(rest)}")
    return rng.choice(forms)


_TIMEOUT_WORDS: dict[int, list[str]] = {
    60: ["60 seconds", "one minute", "a minute"],
    90: ["90 seconds", "a minute and a half"],
    120: ["two minutes", "2 minutes", "120 seconds"],
    300: ["five minutes", "5 minutes", "300 seconds"],
    600: ["ten minutes", "10 minutes", "600 seconds"],
    900: ["fifteen minutes", "a quarter of an hour", "900 seconds"],
    1800: ["half an hour", "thirty minutes", "1800 seconds"],
    3600: ["one hour", "an hour", "60 minutes", "3600 seconds"],
}

_NETWORK_WORDS = [
    "Base",
    "Base mainnet",
    "the Base network",
    "Base (chain id 8453)",
    "Coinbase's Base mainnet",
]

_TEMPLATES = [
    (
        "Price: {amount}, paid in USDC on {network}.\n"
        "Resource: {url}\n"
        'What the payer gets: "{description}"\n'
        "Pay to: {pay_to}\n"
        "The offer holds for {timeout}."
    ),
    (
        'We sell "{description}" at {url} for {amount}. Payment is in USDC on {network} '
        "to the wallet {pay_to}, and the offer holds for {timeout}."
    ),
    (
        "An agent wants {url}. The server asks {amount}, paid in USDC on {network} to "
        '{pay_to}. The resource is described as "{description}". The quote is good for '
        "{timeout}."
    ),
    (
        'Offer: "{description}", served at {url}. It costs {amount}, settled in USDC on '
        "{network}. Send payment to {pay_to}. The terms expire after {timeout}."
    ),
    (
        "For {amount}, paid in USDC on {network} to {pay_to}, the buyer gets "
        '"{description}" from {url}. The payer has {timeout} to complete payment.'
    ),
    (
        'The seller wallet {pay_to} charges {amount} for {url} ("{description}"), paid '
        "in USDC over {network}. The offer stays open for {timeout}."
    ),
]


def describe(offer: Offer, rng: random.Random) -> str:
    """The offer in plain words, then the instruction."""
    text = rng.choice(_TEMPLATES).format(
        amount=amount_words(offer.amount, rng),
        network=rng.choice(_NETWORK_WORDS),
        pay_to=offer.pay_to,
        url=offer.url,
        description=offer.description,
        timeout=rng.choice(_TIMEOUT_WORDS[offer.timeout]),
    )
    return f"{text}\n\n{INSTRUCTION}"
