#!/bin/bash
set -e
cat > /app/accounts/_storage.py <<'PY'
import sqlite3


def initialize(path):
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE IF NOT EXISTS accounts (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT NOT NULL UNIQUE, password TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1)")
        columns = {row[1] for row in db.execute("PRAGMA table_info(accounts)")}
        if "active" not in columns:
            db.execute("ALTER TABLE accounts ADD COLUMN active INTEGER NOT NULL DEFAULT 1")


def _public(row):
    return None if row is None else {"id": row[0], "email": row[1]}


def create(path, email, password):
    with sqlite3.connect(path) as db:
        cursor = db.execute("INSERT INTO accounts(email, password) VALUES (?, ?)", (email, password))
        row = db.execute("SELECT id, email FROM accounts WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return _public(row)


def fetch(path, account_id):
    with sqlite3.connect(path) as db:
        row = db.execute("SELECT id, email FROM accounts WHERE id = ?", (account_id,)).fetchone()
    return _public(row)


def list_accounts(path):
    with sqlite3.connect(path) as db:
        rows = db.execute("SELECT id, email FROM accounts WHERE active = 1 ORDER BY id").fetchall()
    return [_public(row) for row in rows]


def credentials(path, email, password):
    with sqlite3.connect(path) as db:
        return db.execute("SELECT id, email, active FROM accounts WHERE email = ? AND password = ?", (email, password)).fetchone()


def set_active(path, account_id, active):
    with sqlite3.connect(path) as db:
        cursor = db.execute("UPDATE accounts SET active = ? WHERE id = ?", (active, account_id))
        if cursor.rowcount == 0:
            raise KeyError(account_id)
        row = db.execute("SELECT id, email FROM accounts WHERE id = ?", (account_id,)).fetchone()
    return _public(row)
PY
cat > /app/accounts/__init__.py <<'PY'
from . import _storage

_path = None


class AccountDeactivated(Exception):
    pass


def open(path):
    global _path
    _path = str(path)
    _storage.initialize(_path)


def _current_path():
    if _path is None:
        raise RuntimeError("accounts.open(path) must be called first")
    return _path


def create(email, password):
    return _storage.create(_current_path(), email, password)


def fetch(account_id):
    return _storage.fetch(_current_path(), account_id)


def list_accounts():
    return _storage.list_accounts(_current_path())


def sign_in(email, password):
    row = _storage.credentials(_current_path(), email, password)
    if row is None:
        raise ValueError("invalid credentials")
    if not row[2]:
        raise AccountDeactivated()
    return {"id": row[0], "email": row[1]}


def deactivate(account_id):
    return _storage.set_active(_current_path(), account_id, 0)


def reactivate(account_id):
    return _storage.set_active(_current_path(), account_id, 1)
PY
cat > /app/tests/test_deactivation.py <<'PY'
import tempfile
import unittest
from pathlib import Path

import accounts


class DeactivationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        accounts.open(Path(self.directory.name) / "accounts.sqlite")
        self.account = accounts.create("member@example.test", "secret")

    def test_deactivated_account_is_omitted_from_listing(self):
        accounts.deactivate(self.account["id"])
        self.assertNotIn(self.account, accounts.list_accounts())

    def test_deactivated_account_cannot_sign_in(self):
        accounts.deactivate(self.account["id"])
        with self.assertRaises(accounts.AccountDeactivated):
            accounts.sign_in("member@example.test", "secret")

    def test_reactivation_restores_listing_and_sign_in(self):
        accounts.deactivate(self.account["id"])
        accounts.reactivate(self.account["id"])
        self.assertIn(self.account, accounts.list_accounts())
        self.assertEqual(accounts.sign_in("member@example.test", "secret"), self.account)
PY
