import json
from pathlib import Path


RECORDS = {}
_path = None


def open_store(path):
    global _path
    _path = Path(path)
    RECORDS.clear()
    if _path.exists():
        RECORDS.update(json.loads(_path.read_text(encoding="utf-8")))


def save():
    if _path is None:
        raise RuntimeError("parcelbox.open(path) must be called first")
    _path.parent.mkdir(parents=True, exist_ok=True)
    _path.write_text(json.dumps(RECORDS, sort_keys=True), encoding="utf-8")
