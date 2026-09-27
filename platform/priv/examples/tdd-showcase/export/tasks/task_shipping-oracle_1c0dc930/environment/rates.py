"""Project-owned shipping rates, expressed in cents and percentages."""

WEIGHT_BANDS = (
    (1, 600),
    (5, 1000),
    (20, 1800),
)

ZONE_MULTIPLIERS_PERCENT = {
    "local": 100,
    "regional": 125,
    "remote": 160,
}

FRAGILE_SURCHARGE_CENTS = 350
