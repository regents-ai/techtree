from . import _storage

_path = None


def open(path):
    global _path
    _path = str(path)
    _storage.initialize(_path)


def _require_open():
    if _path is None:
        raise RuntimeError("accounts.open(path) must be called first")
    return _path


def create(email, password):
    return _storage.create(_require_open(), email, password)


def fetch(account_id):
    return _storage.fetch(_require_open(), account_id)


def list_accounts():
    return _storage.list_accounts(_require_open())


def sign_in(email, password):
    account = _storage.authenticate(_require_open(), email, password)
    if account is None:
        raise ValueError("invalid credentials")
    return account
