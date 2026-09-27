import os
import sqlite3

_database = None
_mode = os.environ.get("ACCOUNT_VARIANT", "correct")


class AccountDeactivated(Exception):
    pass


def open(path):
    global _database
    _database = str(path)
    with sqlite3.connect(_database) as db:
        db.execute("CREATE TABLE IF NOT EXISTS principals (uid INTEGER PRIMARY KEY AUTOINCREMENT, address TEXT UNIQUE NOT NULL, secret TEXT NOT NULL)")
        db.execute("CREATE TABLE IF NOT EXISTS state_journal (sequence INTEGER PRIMARY KEY AUTOINCREMENT, subject INTEGER NOT NULL, state TEXT NOT NULL)")


def _db():
    if _database is None:
        raise RuntimeError("accounts.open(path) must be called first")
    return sqlite3.connect(_database)


def _account(row):
    return None if row is None else {"id": row[0], "email": row[1]}


def _state(connection, account_id):
    row = connection.execute("SELECT state FROM state_journal WHERE subject = ? ORDER BY sequence DESC LIMIT 1", (account_id,)).fetchone()
    return None if row is None else row[0]


def create(email, password):
    with _db() as db:
        cursor = db.execute("INSERT INTO principals(address, secret) VALUES (?, ?)", (email, password))
        account_id = cursor.lastrowid
        db.execute("INSERT INTO state_journal(subject, state) VALUES (?, 'enabled')", (account_id,))
        row = db.execute("SELECT uid, address FROM principals WHERE uid = ?", (account_id,)).fetchone()
    return _account(row)


def fetch(account_id):
    with _db() as db:
        row = db.execute("SELECT uid, address FROM principals WHERE uid = ?", (account_id,)).fetchone()
    return _account(row)


def list_accounts():
    with _db() as db:
        rows = db.execute("SELECT uid, address FROM principals ORDER BY uid").fetchall()
        if _mode != "listing":
            rows = [row for row in rows if _state(db, row[0]) == "enabled"]
    return [_account(row) for row in rows]


def sign_in(email, password):
    with _db() as db:
        row = db.execute("SELECT uid, address FROM principals WHERE address = ? AND secret = ?", (email, password)).fetchone()
        if row is None:
            raise ValueError("invalid credentials")
        if _mode != "signin" and _state(db, row[0]) == "disabled":
            raise AccountDeactivated()
    return _account(row)


def _transition(account_id, state):
    with _db() as db:
        row = db.execute("SELECT uid, address FROM principals WHERE uid = ?", (account_id,)).fetchone()
        if row is None:
            raise KeyError(account_id)
        if not (_mode == "reactivate" and state == "enabled"):
            db.execute("INSERT INTO state_journal(subject, state) VALUES (?, ?)", (account_id, state))
    return _account(row)


def deactivate(account_id):
    return _transition(account_id, "disabled")


def reactivate(account_id):
    return _transition(account_id, "enabled")
