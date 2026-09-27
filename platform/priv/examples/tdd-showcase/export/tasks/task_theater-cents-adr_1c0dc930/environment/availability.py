"""In-memory seat availability for the sample theater-sales package."""

_SHOW_SEATS = {
    "hamlet-evening": {"A1", "A2", "A3", "B1", "B2", "B3"},
    "hamlet-matinee": {"C1", "C2", "C3", "D1"},
}
_held = {show_id: set() for show_id in _SHOW_SEATS}


class Unavailable(Exception):
    pass


def take(show_id, seat_ids):
    """Atomically remove seats from availability or raise Unavailable."""
    requested = tuple(seat_ids)
    known = _SHOW_SEATS.get(show_id, set())
    unavailable = (
        len(set(requested)) != len(requested)
        or any(seat_id not in known for seat_id in requested)
        or any(seat_id in _held.get(show_id, set()) for seat_id in requested)
    )
    if unavailable:
        raise Unavailable(requested)
    _held[show_id].update(requested)
