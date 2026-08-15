"""The commit stamped into a built artifact. Decisions document 0026.

Three things have to hold for a stamp to be worth reading. The build has to
refuse when it cannot establish which commit it is building, so that a wheel
never carries a guess. The bytes it writes have to be the bytes the package
knows how to read, because the two are written in different places — the build
hook cannot import the package it is building. And a wheel nobody has installed
yet has to be readable, because that is what the release checker compares a
bootstrap document against.
"""

from __future__ import annotations

import importlib.util
import zipfile
from pathlib import Path
from typing import Any

import pytest

from techtree.errors import ValidationError
from techtree.release.provenance import (
    BUILD_PROVENANCE_FILENAME,
    BuildProvenance,
    packaged_build_provenance,
    parse_build_provenance,
    render_build_provenance,
    wheel_build_provenance,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
COMMIT = "a3f5c1d2e4b60718293a4b5c6d7e8f9012345678"


def _load_hook() -> Any:
    """Import the build hook, which is a script rather than a package."""
    location = REPOSITORY_ROOT / "tools" / "stamp_provenance.py"
    spec = importlib.util.spec_from_file_location("techtree_stamp_provenance", location)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


#: Loaded once, so that the exception class a test catches is the class the
#: module raises.
HOOK: Any = _load_hook()


def hook() -> Any:
    """Return the loaded build hook module."""
    return HOOK


def stamp(commit: str = COMMIT) -> BuildProvenance:
    return BuildProvenance(
        schema_version="techtree.build-provenance.v1", source_commit=commit
    )


def test_the_build_writes_the_bytes_the_package_reads() -> None:
    """The hook cannot import the package it builds, so this is the seam."""
    assert hook()._stamp_bytes(COMMIT) == render_build_provenance(stamp())


def test_one_commit_has_one_spelling() -> None:
    """Same commit, same bytes: two builds of it are byte-identical."""
    assert render_build_provenance(stamp()) == render_build_provenance(stamp())
    assert render_build_provenance(stamp()).endswith(b"}\n")


def test_a_build_that_cannot_name_its_commit_fails(tmp_path: Path) -> None:
    """No git, no wheel. There is no unknown value to fall back to."""
    with pytest.raises(hook().BuildProvenanceError, match="which commit"):
        hook().source_commit(tmp_path)


def test_an_abbreviated_commit_is_not_a_stamp() -> None:
    with pytest.raises(ValidationError, match="not a valid build provenance"):
        parse_build_provenance(
            b'{"schema_version": "techtree.build-provenance.v1", '
            b'"source_commit": "a3f5c1d"}\n'
        )


def test_a_stamp_round_trips_through_its_stored_bytes() -> None:
    assert parse_build_provenance(render_build_provenance(stamp())) == stamp()


def test_a_wheel_carries_its_stamp_where_the_checker_looks(tmp_path: Path) -> None:
    wheel = tmp_path / "techtree-0.1.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(
            f"techtree/resources/release/{BUILD_PROVENANCE_FILENAME}",
            render_build_provenance(stamp()),
        )

    read = wheel_build_provenance(wheel)
    assert read is not None
    assert read.source_commit == COMMIT


def test_a_wheel_with_no_stamp_reports_none_rather_than_a_commit(
    tmp_path: Path,
) -> None:
    wheel = tmp_path / "techtree-0.1.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("techtree/__init__.py", b"")

    assert wheel_build_provenance(wheel) is None


def test_a_source_checkout_is_not_a_built_artifact() -> None:
    """These tests run from the tree, which nothing stamped, and that is said."""
    assert packaged_build_provenance() is None
