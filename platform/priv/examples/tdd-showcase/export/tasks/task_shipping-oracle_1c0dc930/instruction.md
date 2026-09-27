Complete the local fulfillment package and add its automated tests.

The initial input files are:

  /app/SPEC.txt
  /app/fulfillment/__init__.py
  /app/fulfillment/rates.py
  /app/fulfillment/quote.py

Implement the public shipping quote function in /app/fulfillment/quote.py and create a Python unittest suite in /app/tests/test_quote.py covering the shipping quote behavior. The quote function takes its weight bands, zone multipliers and fragile surcharge from /app/fulfillment/rates.py.

Only Python 3.12 and its standard library are available. The test suite must run successfully with:

  python -m unittest discover -s /app/tests -p 'test*.py'

Leave these completed files:

  /app/fulfillment/quote.py
  /app/tests/test_quote.py
