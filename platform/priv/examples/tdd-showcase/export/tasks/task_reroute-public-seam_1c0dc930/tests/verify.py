import io
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ORIGINAL_IDS = {
    "test_existing.ExistingParcelServiceTests.test_create_places_route",
    "test_existing.ExistingParcelServiceTests.test_dispatch_marks_record",
}


def fail(message):
    print(message.replace("\n", " "))
    raise SystemExit(1)


def check_submission_behavior():
    probe = r'''
import tempfile
from pathlib import Path
import parcelbox

with tempfile.TemporaryDirectory() as directory:
    store = Path(directory) / "service.data"
    parcelbox.open(store)
    parcelbox.create_parcel("waiting", "North")
    result = parcelbox.reroute("waiting", "South")
    assert result == "South"
    assert parcelbox.destination("waiting") == "South"
    parcelbox.open(store)
    assert parcelbox.destination("waiting") == "South"

    parcelbox.create_parcel("sent", "East")
    parcelbox.dispatch("sent")
    try:
        parcelbox.reroute("sent", "West")
    except parcelbox.ParcelDispatchedError:
        pass
    else:
        raise AssertionError("dispatched parcel was rerouted")
    assert parcelbox.destination("sent") == "East"

    try:
        parcelbox.reroute("missing", "Central")
    except parcelbox.UnknownParcelError:
        pass
    else:
        raise AssertionError("unknown parcel did not raise")
'''
    env = dict(os.environ)
    env["PYTHONPATH"] = "/app"
    with tempfile.TemporaryDirectory() as work:
        completed = subprocess.run(
            [sys.executable, "-c", probe],
            cwd=work,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    if completed.returncode != 0:
        fail("The exported parcel service does not implement all specified rerouting outcomes.")


def implementation_source(mode):
    if mode == "noop":
        reroute_body = '''
    record = _record(parcel_id)
    if record[1]:
        raise ParcelDispatchedError(parcel_id)
    return record[0]
'''
    elif mode == "over":
        reroute_body = '''
    record = _record(parcel_id)
    _data[parcel_id] = (destination, record[1])
    _save()
    return destination
'''
    else:
        reroute_body = '''
    record = _record(parcel_id)
    if record[1]:
        raise ParcelDispatchedError(parcel_id)
    _data[parcel_id] = (destination, False)
    _save()
    return destination
'''
    return textwrap.dedent('''
        from pathlib import Path

        class UnknownParcelError(LookupError):
            pass

        class ParcelDispatchedError(RuntimeError):
            pass

        _location = None
        _data = {}

        def open(path):
            global _location
            _location = Path(path)
            _data.clear()
            if _location.exists():
                for line in _location.read_text(encoding="utf-8").splitlines():
                    parcel_id, dispatched, destination_value = line.split("|", 2)
                    _data[parcel_id] = (destination_value, dispatched == "sent")

        def _save():
            _location.parent.mkdir(parents=True, exist_ok=True)
            lines = []
            for parcel_id in sorted(_data):
                destination_value, dispatched = _data[parcel_id]
                lines.append(parcel_id + "|" + ("sent" if dispatched else "waiting") + "|" + destination_value)
            _location.write_text("\\n".join(lines), encoding="utf-8")

        def _record(parcel_id):
            try:
                return _data[parcel_id]
            except KeyError:
                raise UnknownParcelError(parcel_id) from None

        def create_parcel(parcel_id, destination):
            _data[parcel_id] = (destination, False)
            _save()
            return parcel_id

        def dispatch(parcel_id):
            record = _record(parcel_id)
            _data[parcel_id] = (record[0], True)
            _save()

        def destination(parcel_id):
            return _record(parcel_id)[0]

        def reroute(parcel_id, destination):
    ''') + textwrap.indent(textwrap.dedent(reroute_body).strip("\n") + "\n", "    ")


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def run_submitted_tests(implementation):
    os.chdir(tempfile.mkdtemp(prefix="parcelbox-tests-"))
    retained = []
    for entry in sys.path:
        if entry in ("", "/app") or entry.startswith("/app/"):
            continue
        retained.append(entry)
    sys.path[:] = ["/app/tests", implementation] + retained
    suite = unittest.defaultTestLoader.discover(
        "/app/tests", pattern="test*.py", top_level_dir="/app/tests"
    )
    submitted = [case for case in flatten(suite) if case.id() not in ORIGINAL_IDS]
    if not submitted:
        print("NO_SUBMITTED_TESTS")
        return 2
    selected = unittest.TestSuite(submitted)
    result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(selected)
    return 0 if result.wasSuccessful() else 1


def child_result(implementation):
    completed = subprocess.run(
        [sys.executable, __file__, "--run-tests", implementation],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.returncode, completed.stdout


def main():
    check_submission_behavior()
    with tempfile.TemporaryDirectory(prefix="parcelbox-variants-") as directory:
        roots = {}
        for mode in ("noop", "over", "alternate"):
            root = Path(directory) / mode
            package = root / "parcelbox"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text(implementation_source(mode), encoding="utf-8")
            roots[mode] = str(root)

        code, output = child_result("/app")
        if code == 2 or "NO_SUBMITTED_TESTS" in output:
            fail("No submitted unittest cases were found beyond the original suite.")
        if code != 0:
            fail("The submitted tests do not pass against the submitted implementation.")

        code, _ = child_result(roots["noop"])
        if code == 0:
            fail("The submitted tests do not detect a reroute operation that leaves the destination unchanged.")

        code, _ = child_result(roots["over"])
        if code == 0:
            fail("The submitted tests do not detect rerouting of a dispatched parcel.")

        code, _ = child_result(roots["alternate"])
        if code != 0:
            fail("The submitted tests do not pass against the behavior-equivalent alternate parcel service.")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--run-tests":
        raise SystemExit(run_submitted_tests(sys.argv[2]))
    main()
