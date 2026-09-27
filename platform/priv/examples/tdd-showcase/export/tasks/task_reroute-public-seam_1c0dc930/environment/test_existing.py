import tempfile
import unittest
from pathlib import Path

import parcelbox


class ExistingParcelServiceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        parcelbox.open(Path(self.tempdir.name) / "parcels.json")

    def test_create_places_route(self):
        parcelbox.create_parcel("P-100", "North Depot")
        from parcelbox import _routing
        self.assertEqual(_routing.ROUTES["P-100"], "North Depot")

    def test_dispatch_marks_record(self):
        parcelbox.create_parcel("P-200", "South Depot")
        parcelbox.dispatch("P-200")
        from parcelbox import _persistence
        self.assertTrue(_persistence.RECORDS["P-200"]["dispatched"])
