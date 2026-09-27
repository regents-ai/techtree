#!/bin/bash
set -e
bash /solution/solve.sh
cat > /app/tests/test_deactivation.py <<'PY'
import sqlite3
import tempfile
import unittest
from pathlib import Path

import accounts


class DeactivationStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = Path(self.temp.name) / "accounts.sqlite"
        accounts.open(self.database)
        self.account = accounts.create("member@example.test", "secret")

    def test_deactivate_sets_active_flag(self):
        accounts.deactivate(self.account["id"])
        with sqlite3.connect(self.database) as connection:
            active = connection.execute("SELECT active FROM accounts WHERE id = ?", (self.account["id"],)).fetchone()[0]
        self.assertEqual(active, 0)

    def test_reactivate_sets_active_flag(self):
        accounts.deactivate(self.account["id"])
        accounts.reactivate(self.account["id"])
        with sqlite3.connect(self.database) as connection:
            active = connection.execute("SELECT active FROM accounts WHERE id = ?", (self.account["id"],)).fetchone()[0]
        self.assertEqual(active, 1)
PY
