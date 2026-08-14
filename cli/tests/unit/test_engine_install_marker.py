"""The install marker protocol. Decisions 0004, ratified as 0007 R7.

An engine directory can be missing for two very different reasons: nobody ever
installed one, or somebody was installing one and the machine stopped. The
marker is what tells those apart, and these tests are about that distinction
holding in every state a killed install can leave behind.

Nothing here runs ``uv``. The states are written directly — a marker with no
engine beside it, a half-copied directory, a marker left next to a finished
install, a marker nobody can read — because that is exactly what a power cut
leaves, and arranging it is more honest than killing a real install and hoping
it dies at the right moment. What a real install does with the marker — writes
it first, removes it after publishing, and takes it with it when it fails —
belongs to ``tests/integration/test_engine_install.py``, because only a real
one can prove it.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from techtree.canonical import validate_digest
from techtree.engines.installer import (
    INSTALLING_MARKER_PREFIX,
    EngineInstaller,
)
from techtree.engines.installer import _excerpt as installer_excerpt
from techtree.engines.registry import EngineRegistry
from techtree.fs import atomic_write_json
from techtree.models.base import Digest
from techtree.models.engine import EngineInstallation
from techtree.paths import TechtreePaths, ensure_path_layout, paths_from_root
from techtree.settings import Settings

DIGEST: Digest = validate_digest(f"sha256:{'a' * 64}")
OTHER: Digest = validate_digest(f"sha256:{'b' * 64}")


@pytest.fixture
def paths(temp_techtree_home: Path) -> TechtreePaths:
    resolved = paths_from_root(temp_techtree_home)
    ensure_path_layout(resolved)
    return resolved


@pytest.fixture
def installer(paths: TechtreePaths) -> EngineInstaller:
    """An installer that can inspect a home without being able to build one.

    ``uv`` is never invoked by anything under test here, and naming a path
    that does not exist makes that a fact rather than an intention.
    """
    return EngineInstaller(
        paths, EngineRegistry(paths, Settings()), paths.root / "no-such-uv"
    )


def marker_path(paths: TechtreePaths, digest: Digest) -> Path:
    """Return where the installer writes one engine's marker."""
    directory = paths.engine_dir(digest).name
    return paths.engines_dir / f"{INSTALLING_MARKER_PREFIX}{directory}"


def start_an_install(
    paths: TechtreePaths, digest: Digest, *, files: bool = True
) -> Path:
    """Leave behind exactly what a killed install leaves behind."""
    atomic_write_json(
        marker_path(paths, digest),
        {
            "schema_version": "techtree.engine-installing.v1",
            "digest": digest,
            "started_at": "2026-08-13T09:00:00Z",
            "pid": 4321,
        },
    )
    engine = paths.engine_dir(digest)
    if files:
        (engine / ".venv" / "bin").mkdir(parents=True)
        (engine / "uv.lock").write_text("half a lock\n", encoding="utf-8")
    return engine


def finish_an_install(paths: TechtreePaths, digest: Digest) -> None:
    """Write the one signal that publishes an installation."""
    EngineRegistry(paths, Settings()).record(
        EngineInstallation(
            digest=digest,
            installed_at=datetime.now(UTC),
            python_executable=str(
                paths.engine_dir(digest) / ".venv" / "bin" / "python"
            ),
            descriptor_digest=OTHER,
            verified=True,
        )
    )


# ---------------------------------------------------------------------------
# What the marker distinguishes
# ---------------------------------------------------------------------------


def test_a_machine_that_never_installed_anything_reports_nothing(
    installer: EngineInstaller,
) -> None:
    assert installer.interrupted_installs() == []
    assert installer.discard_interrupted() == []


def test_an_install_that_was_killed_is_found_and_named(
    paths: TechtreePaths, installer: EngineInstaller
) -> None:
    """The marker says which engine, and when the attempt started."""
    engine = start_an_install(paths, DIGEST)

    found = installer.interrupted_installs()

    assert [install.digest for install in found] == [DIGEST]
    assert found[0].path == engine
    assert found[0].started_at == "2026-08-13T09:00:00Z"
    assert found[0].pid == 4321


def test_a_marker_with_no_directory_beside_it_still_counts(
    paths: TechtreePaths, installer: EngineInstaller
) -> None:
    """An install killed between announcing itself and creating anything."""
    start_an_install(paths, DIGEST, files=False)

    assert [install.digest for install in installer.interrupted_installs()] == [DIGEST]


def test_a_marker_nobody_can_read_still_means_what_a_marker_means(
    paths: TechtreePaths, installer: EngineInstaller
) -> None:
    """The marker's existence is the signal; its contents are diagnostics."""
    start_an_install(paths, DIGEST)
    marker_path(paths, DIGEST).write_bytes(b"\x00not json at all")

    found = installer.interrupted_installs()

    assert [install.digest for install in found] == [DIGEST]
    assert found[0].started_at is None
    assert found[0].pid is None


def test_a_complete_installation_is_never_reported_as_interrupted(
    paths: TechtreePaths, installer: EngineInstaller
) -> None:
    """A marker beside installed.json is residue, not unfinished work.

    ``installed.json`` is the only publication signal, so an install that
    wrote one and then lost the machine before tidying up is installed. What
    is left is a stray file, and rebuilding a working engine because of one
    would be the marker protocol doing harm.
    """
    start_an_install(paths, DIGEST)
    finish_an_install(paths, DIGEST)

    assert installer.interrupted_installs() == []


def test_an_installed_engine_without_a_marker_is_left_alone(
    paths: TechtreePaths, installer: EngineInstaller
) -> None:
    start_an_install(paths, DIGEST)
    finish_an_install(paths, DIGEST)
    marker_path(paths, DIGEST).unlink()

    assert installer.interrupted_installs() == []
    assert installer.discard_interrupted() == []


# ---------------------------------------------------------------------------
# What discarding does
# ---------------------------------------------------------------------------


def test_discarding_removes_the_unfinished_directory_and_its_marker(
    paths: TechtreePaths, installer: EngineInstaller
) -> None:
    """Decisions 0004 step 5: an interrupted install is rebuilt, not resumed."""
    engine = start_an_install(paths, DIGEST)

    discarded = installer.discard_interrupted()

    assert [install.digest for install in discarded] == [DIGEST]
    assert not engine.exists()
    assert not marker_path(paths, DIGEST).exists()
    assert installer.interrupted_installs() == []


def test_discarding_clears_a_stray_marker_but_keeps_the_installation(
    paths: TechtreePaths, installer: EngineInstaller
) -> None:
    """The other order, for the other state: the marker goes, the engine stays."""
    start_an_install(paths, DIGEST)
    finish_an_install(paths, DIGEST)

    assert installer.discard_interrupted() == []
    assert not marker_path(paths, DIGEST).exists()
    assert EngineRegistry(paths, Settings()).installation(DIGEST) is not None


def test_one_unfinished_install_does_not_disturb_another_engine(
    paths: TechtreePaths, installer: EngineInstaller
) -> None:
    """Markers name one engine each, so discarding is not a sweep."""
    unfinished = start_an_install(paths, DIGEST)
    working = start_an_install(paths, OTHER)
    finish_an_install(paths, OTHER)

    discarded = installer.discard_interrupted()

    assert [install.digest for install in discarded] == [DIGEST]
    assert not unfinished.exists()
    assert working.exists()
    assert EngineRegistry(paths, Settings()).installation(OTHER) is not None


def test_a_file_techtree_did_not_write_is_not_treated_as_a_marker(
    paths: TechtreePaths, installer: EngineInstaller
) -> None:
    """Only markers naming an engine digest are Techtree's to act on."""
    stray = paths.engines_dir / f"{INSTALLING_MARKER_PREFIX}something-else"
    stray.write_text("{}\n", encoding="utf-8")
    notes = paths.engines_dir / "notes.txt"
    notes.write_text("mine\n", encoding="utf-8")

    assert installer.interrupted_installs() == []
    assert installer.discard_interrupted() == []
    assert stray.exists()
    assert notes.exists()


def test_the_marker_says_which_engine_it_is_about(paths: TechtreePaths) -> None:
    """A reader who finds one should not have to guess what it belongs to."""
    start_an_install(paths, DIGEST)

    document = json.loads(marker_path(paths, DIGEST).read_text("utf-8"))

    assert document["digest"] == DIGEST
    assert marker_path(paths, DIGEST).name.endswith(paths.engine_dir(DIGEST).name)


# ---------------------------------------------------------------------------
# What a failed uv step is allowed to quote back. WP11g S1.
# ---------------------------------------------------------------------------
#
# Installation is the one step that runs a subprocess with the caller's own
# environment, because uv needs their proxy, certificate and index settings to
# reach a network they can reach. That makes uv's output the one text in this
# package written by somebody else, and a private index URL carries its
# credential inline. The excerpt is where that output becomes Techtree's, so
# it is where the scrubbing has to happen.

#: A private index, spelled the way uv reports one back.
_INDEX_URL_WITH_TOKEN = "https://deploy:s3cr3t-p4ss@pypi.corp.example/simple"


def test_a_uv_excerpt_is_scrubbed_before_it_becomes_techtree_text() -> None:
    excerpt = installer_excerpt(
        f"  error: failed to fetch from {_INDEX_URL_WITH_TOKEN}\n"
    )

    assert "s3cr3t-p4ss" not in excerpt
    assert "deploy" not in excerpt
    # The host survives, because which index refused them is the diagnosis.
    assert "pypi.corp.example/simple" in excerpt


def test_a_uv_excerpt_keeps_the_tail_where_the_reason_is() -> None:
    excerpt = installer_excerpt("noise\n" * 4000 + "error: the actual reason\n")

    assert excerpt.startswith("...")
    assert excerpt.endswith("error: the actual reason")
