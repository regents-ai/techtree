#!/bin/bash
set -e
cat > /app/parcelbox/__init__.py <<'PY'
from pathlib import Path
from . import _persistence, _routing


class UnknownParcelError(LookupError):
    pass


class ParcelDispatchedError(RuntimeError):
    pass


def open(path):
    _persistence.open_store(Path(path))


def _find(parcel_id):
    try:
        return _persistence.RECORDS[parcel_id]
    except KeyError:
        raise UnknownParcelError(parcel_id) from None


def create_parcel(parcel_id, destination):
    _persistence.RECORDS[parcel_id] = {"destination": destination, "dispatched": False}
    _persistence.save()
    return parcel_id


def dispatch(parcel_id):
    _find(parcel_id)["dispatched"] = True
    _persistence.save()


def destination(parcel_id):
    return _find(parcel_id)["destination"]


def reroute(parcel_id, destination):
    parcel = _find(parcel_id)
    if parcel["dispatched"]:
        raise ParcelDispatchedError(parcel_id)
    parcel["destination"] = destination
    _persistence.save()
    return destination
PY
cat > /app/tests/test_reroute.py <<'PY'
import tempfile
import unittest
from pathlib import Path

from parcelbox import (
    ParcelDispatchedError,
    UnknownParcelError,
    create_parcel,
    destination,
    dispatch,
    open,
    reroute,
)


class ParcelReroutingBehavior(unittest.TestCase):
    def test_rerouting_outcomes(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Path(directory) / "box"
            open(store)

            create_parcel("ready", "A")
            self.assertEqual("B", reroute("ready", "B"))
            self.assertEqual("B", destination("ready"))
            open(store)
            self.assertEqual("B", destination("ready"))

            create_parcel("gone", "C")
            dispatch("gone")
            with self.assertRaises(ParcelDispatchedError):
                reroute("gone", "D")
            self.assertEqual("C", destination("gone"))

            with self.assertRaises(UnknownParcelError):
                reroute("never-created", "E")
PY
