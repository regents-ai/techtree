Implement the request in /app/ISSUE.md for the notifier package and add an automated test suite.

The input files are:

/app/ISSUE.md
/app/notifier/__init__.py
/app/notifier/errors.py
/app/notifier/backoff.py
/app/notifier/service.py

Modify and leave the completed implementation at:

/app/notifier/service.py

Create and leave the test suite at:

/app/tests/test_notifier.py

Use only Python's standard library. The suite must be runnable from /app with:

python3 -m unittest discover -s /app/tests -p 'test*.py'

The suite must pass offline, with no network access, in under five seconds.
