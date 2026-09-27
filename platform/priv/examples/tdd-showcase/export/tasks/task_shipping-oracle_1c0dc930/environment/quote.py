"""Shipping quote API."""

from . import rates


def quote(weight_kg, zone, fragile=False):
    """Return the shipping charge in cents."""
    raise NotImplementedError("shipping quote rules are not implemented")
