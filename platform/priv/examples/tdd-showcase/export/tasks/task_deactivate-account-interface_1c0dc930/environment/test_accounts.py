import sqlite3
import tempfile
import unittest
from pathlib import Path

import accounts


class AccountTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name) / "accounts.sqlite"
        accounts.open(self.database)

    def test_create_can_be_fetched(self):
        created = accounts.create("alice@example.test", "secret")
        self.assertEqual(accounts.fetch(created["id"]), created)

    def test_list_contains_created_accounts(self):
        accounts.create("alice@example.test", "secret")
        accounts.create("bob@example.test", "hunter2")
        with sqlite3.connect(self.database) as connection:
            rows = connection.execute(
                "SELECT email FROM accounts ORDER BY id"
            ).fetchall()
        self.assertEqual(rows, [("alice@example.test",), ("bob@example.test",)])

    def test_sign_in_returns_stored_account(self):
        created = accounts.create("alice@example.test", "secret")
        with sqlite3.connect(self.database) as connection:
            stored_password = connection.execute(
                "SELECT password FROM accounts WHERE id = ?", (created["id"],)
            ).fetchone()[0]
        self.assertEqual(stored_password, "secret")
        self.assertEqual(accounts.sign_in("alice@example.test", "secret"), created)


if __name__ == "__main__":
    unittest.main()
