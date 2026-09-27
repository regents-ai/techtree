#!/bin/bash
set -e
python - <<'PY'
from pathlib import Path
path = Path('/app/parcelbox/__init__.py')
source = path.read_text(encoding='utf-8')
old = '''def reroute(parcel_id, destination):
    raise NotImplementedError("rerouting is not implemented")
'''
new = '''def reroute(parcel_id, destination):
    if parcel_id not in _persistence.RECORDS:
        raise UnknownParcelError(parcel_id)
    record = _persistence.RECORDS[parcel_id]
    if record["dispatched"]:
        raise ParcelDispatchedError(parcel_id)
    record["destination"] = destination
    _routing.ROUTES[parcel_id] = destination
    _persistence.save()
    return destination
'''
if old not in source:
    raise SystemExit('reroute stub not found')
path.write_text(source.replace(old, new), encoding='utf-8')
PY
cat > /app/tests/test_reroute.py <<'PY'
import tempfile
import unittest
from pathlib import Path

import parcelbox


class RerouteTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = Path(self.directory.name) / "parcels.data"
        parcelbox.open(self.store)

    def test_undispatched_parcel_gets_new_destination(self):
        parcelbox.create_parcel("P-301", "North")
        self.assertEqual(parcelbox.reroute("P-301", "South"), "South")
        self.assertEqual(parcelbox.destination("P-301"), "South")
        parcelbox.open(self.store)
        self.assertEqual(parcelbox.destination("P-301"), "South")

    def test_dispatched_parcel_cannot_be_rerouted(self):
        parcelbox.create_parcel("P-302", "East")
        parcelbox.dispatch("P-302")
        with self.assertRaises(parcelbox.ParcelDispatchedError):
            parcelbox.reroute("P-302", "West")
        self.assertEqual(parcelbox.destination("P-302"), "East")

    def test_unknown_parcel_cannot_be_rerouted(self):
        with self.assertRaises(parcelbox.UnknownParcelError):
            parcelbox.reroute("P-404", "Central")
PY
