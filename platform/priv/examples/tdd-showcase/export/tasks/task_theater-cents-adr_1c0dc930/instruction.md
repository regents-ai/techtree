Complete the theater-sales work item in /app/WORK_ITEM.md.

The repository inputs are:

/app/CONTEXT.md
/app/WORK_ITEM.md
/app/adr/0001-money-at-public-boundaries.md
/app/data/seat_prices.json
/app/theater_sales/__init__.py
/app/theater_sales/availability.py

Implement the requested feature in:

/app/theater_sales/sales.py

Write its public-interface tests using Python's built-in unittest framework in:

/app/tests/test_sales.py

The tests must run offline with:

python -m unittest discover -s /app/tests -p 'test_sales.py'

Use only the Python standard library. Leave both requested files in place when finished.
