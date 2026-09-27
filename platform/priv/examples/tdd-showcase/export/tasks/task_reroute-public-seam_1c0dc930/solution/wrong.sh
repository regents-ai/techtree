#!/bin/bash
set -e
python - <<'PY'
from pathlib import Path
path = Path('/app/parcelbox/__init__.py')
source = path.read_text(encoding='utf-8')
source = source.replace(
'''def reroute(parcel_id, destination):
    raise NotImplementedError("rerouting is not implemented")
''',
'''def reroute(parcel_id, destination):
    if parcel_id not in _persistence.RECORDS:
        raise UnknownParcelError(parcel_id)
    record = _persistence.RECORDS[parcel_id]
    if record["dispatched"]:
        raise ParcelDispatchedError(parcel_id)
    record["destination"] = destination
    _routing.ROUTES[parcel_id] = destination
    _persistence.save()
    return destination
''')
path.write_text(source, encoding='utf-8')
PY
cat > /app/tests/test_reroute.py <<'PY'
import tempfile
import unittest
from pathlib import Path

import parcelbox
from parcelbox import _persistence, _routing


class RerouteStorageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        parcelbox.open(Path(self.directory.name) / "records.json")

    def test_reroute_rewrites_routing_table_and_record(self):
        parcelbox.create_parcel("P-500", "Old")
        parcelbox.reroute("P-500", "New")
        self.assertEqual(_routing.ROUTES["P-500"], "New")
        self.assertEqual(_persistence.RECORDS["P-500"]["destination"], "New")

    def test_dispatch_flag_blocks_reroute(self):
        parcelbox.create_parcel("P-501", "Fixed")
        parcelbox.dispatch("P-501")
        with self.assertRaises(parcelbox.ParcelDispatchedError):
            parcelbox.reroute("P-501", "Moved")
PY
