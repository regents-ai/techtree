Implement the account deactivation ticket in the repository under /app and add automated tests for it.

Read these input files:

/app/TICKET.md
/app/accounts/__init__.py
/app/accounts/_storage.py
/app/tests/test_accounts.py

Leave the completed accounts package in /app/accounts and add the new test file /app/tests/test_deactivation.py. Preserve the existing public behavior described by the current package and tests while adding the ticketed behavior.

The environment has Python 3.12 and the standard library, including sqlite3 and unittest. It has no network access and no third-party test packages. You can run the suite with:

python -m unittest discover -s /app/tests -p 'test*.py'
