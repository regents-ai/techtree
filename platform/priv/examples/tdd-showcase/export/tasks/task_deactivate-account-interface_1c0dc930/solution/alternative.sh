#!/bin/bash
set -e
cat > /app/accounts/_storage.py <<'PY'
import sqlite3


def setup(filename):
    with sqlite3.connect(filename) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS members (member_key INTEGER PRIMARY KEY AUTOINCREMENT, login TEXT UNIQUE NOT NULL, passphrase TEXT NOT NULL)")
        connection.execute("CREATE TABLE IF NOT EXISTS lifecycle (event_key INTEGER PRIMARY KEY AUTOINCREMENT, member_key INTEGER NOT NULL, value TEXT NOT NULL)")


def latest(connection, member_key):
    row = connection.execute("SELECT value FROM lifecycle WHERE member_key = ? ORDER BY event_key DESC LIMIT 1", (member_key,)).fetchone()
    return None if row is None else row[0]
PY
cat > /app/accounts/__init__.py <<'PY'
import sqlite3
from . import _storage

_filename = None


class AccountDeactivated(Exception):
    pass


def open(path):
    global _filename
    _filename = str(path)
    _storage.setup(_filename)


def _connect():
    if _filename is None:
        raise RuntimeError("accounts.open(path) must be called first")
    return sqlite3.connect(_filename)


def _view(row):
    return None if row is None else {"id": row[0], "email": row[1]}


def create(email, password):
    with _connect() as connection:
        cursor = connection.execute("INSERT INTO members(login, passphrase) VALUES (?, ?)", (email, password))
        key = cursor.lastrowid
        connection.execute("INSERT INTO lifecycle(member_key, value) VALUES (?, 'open')", (key,))
        row = connection.execute("SELECT member_key, login FROM members WHERE member_key = ?", (key,)).fetchone()
    return _view(row)


def fetch(account_id):
    with _connect() as connection:
        row = connection.execute("SELECT member_key, login FROM members WHERE member_key = ?", (account_id,)).fetchone()
    return _view(row)


def list_accounts():
    with _connect() as connection:
        rows = connection.execute("SELECT member_key, login FROM members ORDER BY member_key").fetchall()
        rows = [row for row in rows if _storage.latest(connection, row[0]) == "open"]
    return [_view(row) for row in rows]


def sign_in(email, password):
    with _connect() as connection:
        row = connection.execute("SELECT member_key, login FROM members WHERE login = ? AND passphrase = ?", (email, password)).fetchone()
        if row is None:
            raise ValueError("invalid credentials")
        if _storage.latest(connection, row[0]) == "closed":
            raise AccountDeactivated()
    return _view(row)


def _record(account_id, value):
    with _connect() as connection:
        row = connection.execute("SELECT member_key, login FROM members WHERE member_key = ?", (account_id,)).fetchone()
        if row is None:
            raise KeyError(account_id)
        if _storage.latest(connection, account_id) != value:
            connection.execute("INSERT INTO lifecycle(member_key, value) VALUES (?, ?)", (account_id, value))
    return _view(row)


def deactivate(account_id):
    return _record(account_id, "closed")


def reactivate(account_id):
    return _record(account_id, "open")
PY
cat > /app/tests/test_deactivation.py <<'PY'
import tempfile
import unittest
from pathlib import Path

import accounts


class AccountLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        accounts.open(Path(self.temp.name) / "store.db")

    def test_closed_member_is_hidden_and_denied_access(self):
        member = accounts.create("person@example.test", "correct-password")
        accounts.deactivate(member["id"])
        self.assertEqual(accounts.list_accounts(), [])
        with self.assertRaises(accounts.AccountDeactivated):
            accounts.sign_in("person@example.test", "correct-password")

    def test_reopened_member_is_visible_and_can_access_account(self):
        member = accounts.create("person@example.test", "correct-password")
        accounts.deactivate(member["id"])
        accounts.reactivate(member["id"])
        self.assertEqual(accounts.list_accounts(), [member])
        self.assertEqual(accounts.sign_in("person@example.test", "correct-password"), member)
PY
