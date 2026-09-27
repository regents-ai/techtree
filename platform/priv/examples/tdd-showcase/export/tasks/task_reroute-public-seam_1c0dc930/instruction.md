Complete the parcel rerouting feature in the repository and add regression tests for it.

The repository inputs are:

- /app/pyproject.toml
- /app/FEATURE.md
- /app/parcelbox/__init__.py
- /app/parcelbox/_routing.py
- /app/parcelbox/_persistence.py
- /app/tests/test_existing.py

Implement the feature in /app/parcelbox. Add one or more standard-library unittest test files matching test_*.py under /app/tests. Leave the completed package under /app/parcelbox and the complete test suite under /app/tests.

Run the suite with:

python -m unittest discover -s /app/tests -p 'test*.py'
