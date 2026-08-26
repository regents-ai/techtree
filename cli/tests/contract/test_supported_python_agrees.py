"""One supported Python, said in several places, checked to be one answer.

Which Python this release runs on is written down more than once, because
several different readers need it and none of them can see the others' copy:
the package metadata is what an installer obeys, the doctor's range is what a
participant is told, and the published bootstrap document is what the install
command must name. Decision 0034 made the last of those a release check after
two clean-machine journeys found the install and the health check disagreeing.

This is the rest of that fix. A number repeated in three places is one number
until the day somebody moves one of them, and the failure that day is not a
crash: it is an install that succeeds onto an interpreter the product then
refuses. So the copies are compared here, where moving one alone is a red
test rather than a shipped contradiction.

The plugin's own copy is bound to the same value beside its other contract
tests, which is where a sibling checkout is known to exist.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Final

from techtree.doctor.checks import SUPPORTED_PYTHON

#: The repository root, from this file rather than from a working directory.
ROOT: Final = Path(__file__).resolve().parents[2]


def declared_range() -> tuple[tuple[int, int], tuple[int, int]]:
    """Return the Python range the package metadata declares, as versions.

    Parsed rather than pattern-matched against an expected string: the point
    is to read what the package actually says, so that a change to it is
    reflected here instead of asserted away.
    """
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    specifier = metadata["project"]["requires-python"]
    floor, ceiling = (part.strip() for part in specifier.split(","))
    assert floor.startswith(">="), specifier
    assert ceiling.startswith("<"), specifier
    return _version(floor[2:]), _version(ceiling[1:])


def _version(text: str) -> tuple[int, int]:
    major, minor = text.split(".")[:2]
    return int(major), int(minor)


def test_the_doctor_reports_the_range_the_package_declares() -> None:
    """What a participant is told must be what an installer obeys.

    These two disagreeing is worse than either being wrong on its own: an
    installer that accepts an interpreter the doctor rejects produces a
    working install whose first output is a failure, which is exactly the
    report decision 0034 came from.
    """
    assert declared_range() == SUPPORTED_PYTHON
