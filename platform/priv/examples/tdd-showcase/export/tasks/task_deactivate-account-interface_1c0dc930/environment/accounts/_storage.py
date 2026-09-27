import sqlite3


def initialize(path):
    with sqlite3.connect(path) as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL
            )"""
        )


def _public(row):
    if row is None:
        return None
    return {"id": row[0], "email": row[1]}


def create(path, email, password):
    with sqlite3.connect(path) as connection:
        cursor = connection.execute(
            "INSERT INTO accounts(email, password) VALUES (?, ?)",
            (email, password),
        )
        row = connection.execute(
            "SELECT id, email FROM accounts WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    return _public(row)


def fetch(path, account_id):
    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT id, email FROM accounts WHERE id = ?", (account_id,)
        ).fetchone()
    return _public(row)


def list_accounts(path):
    with sqlite3.connect(path) as connection:
        rows = connection.execute(
            "SELECT id, email FROM accounts ORDER BY id"
        ).fetchall()
    return [_public(row) for row in rows]


def authenticate(path, email, password):
    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT id, email FROM accounts WHERE email = ? AND password = ?",
            (email, password),
        ).fetchone()
    return _public(row)
