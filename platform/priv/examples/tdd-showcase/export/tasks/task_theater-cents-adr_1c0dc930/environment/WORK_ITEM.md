# Add seat holds

Create `theater_sales.sales` with this public interface:

- `SeatsUnavailable`, an exception type.
- `hold_seats(show_id, seat_ids)`, which holds all requested seats and returns a new hold ID. If any requested seat does not exist or is already held, raise `SeatsUnavailable` and do not hold any of the requested seats.
- `amount_owed(hold_id)`, which returns the total price of the seats in that hold.

Use the seat catalog at `/app/data/seat_prices.json`. Existing seat availability behavior is in `theater_sales.availability`.

Add tests through the public interface. Include the amount owed for a multi-seat hold and the refusal of a seat that is already held.
