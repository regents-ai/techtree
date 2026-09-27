Implement the converted-price quote described in the existing repository.

Inputs:
- /app/REQUEST.md
- /app/pricing/__init__.py
- /app/pricing/rates.py
- /app/pricing/fees.py
- /app/pricing/rounding.py
- /app/pricing/fee_tiers.json
- /app/tests/__init__.py
- /app/tests/test_fees.py

The container has no outbound network access.

Leave these files:
- /app/pricing/quotes.py, providing the requested public quote_in function.
- /app/tests/test_quotes.py, containing automated tests for the requested behavior that run with Python's standard-library unittest framework.
