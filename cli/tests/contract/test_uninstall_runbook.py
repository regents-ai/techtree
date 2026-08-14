"""What survives an uninstall, and whether the runbook still says so. WP11g B3.

``docs/uninstall-and-data-retention.md`` makes promises about a disk this test
suite cannot see: where a participant's state lives, what a package manager
removes, what it leaves. A promise about disk is worth what its test is worth,
so everything checkable from inside the repository is checked here — and the
checks read the document rather than restating it, so the documentation cannot
drift away from the code while a test that hardcodes the same strings goes on
passing. That is the failure mode this file exists to prevent.

The headline claim is the private signing key. It is one file, an uninstall
does not remove it, deleting it is irreversible, and the runbook has to name it
at exactly the path the identity store writes it to. If those two ever
disagree, somebody follows the runbook, believes their key is gone, and it is
not — or reaches for a path that no longer exists and concludes it already was.

What cannot be checked here is checked nowhere else either, and the last tests
hold the document to *saying* so rather than to implying it: this repository
cannot reach into a model provider's retention, and it cannot recall a proof
bundle somebody already copied elsewhere.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

from techtree.catalog.repository import EmbeddedCatalogRepository, packaged_catalog_root
from techtree.cli.app import create_app
from techtree.identity.store import PRIVATE_KEY_FILENAME, PUBLIC_IDENTITY_FILENAME
from techtree.paths import APPLICATION_NAME, paths_from_root
from techtree.receipts.bundle import BUNDLE_DIRECTORY
from techtree.tasksets.service import TASKSET_DIRECTORY
from techtree.verifiers.models import VERIFIERS_DIRECTORY

REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[2]
RUNBOOK_PATH: Final = REPOSITORY_ROOT / "docs" / "uninstall-and-data-retention.md"
RUNBOOK: Final = RUNBOOK_PATH.read_text(encoding="utf-8")

#: The tree diagram, which is the part of the document a reader navigates by.
_HOME_TREE: Final = re.search(r"```text\n(<techtree-home>/\n.*?)```", RUNBOOK, re.S)


def _home_members() -> set[str]:
    """Return the top-level names the Techtree home actually has.

    Derived from :class:`~techtree.paths.TechtreePaths` rather than listed, so
    a directory added to the home later shows up here as a documentation
    failure on the day it is added.
    """
    root = Path("/techtree-home")
    paths = paths_from_root(root)
    return {
        value.relative_to(root).as_posix()
        for name, value in vars(paths).items()
        if name != "root" and isinstance(value, Path)
    }


# The document exists and describes this build ----------------------------------------


def test_the_runbook_draws_the_home_it_is_about() -> None:
    assert RUNBOOK_PATH.is_file()
    assert _HOME_TREE is not None, "the runbook has no home-layout diagram"


def test_every_directory_the_home_has_is_in_the_diagram() -> None:
    """The anti-drift check: a new home directory must be documented to ship.

    Names are read out of ``TechtreePaths``, so this fails when the code grows
    a directory the runbook does not mention — which is exactly the moment a
    retention promise silently stops being complete.
    """
    assert _HOME_TREE is not None
    diagram = _HOME_TREE.group(1)

    missing = [member for member in sorted(_home_members()) if member not in diagram]

    assert not missing, f"the runbook's diagram omits part of the home: {missing}"


def test_the_diagram_names_the_run_directories_a_run_writes() -> None:
    """The subdirectories hold the transcripts and the proof, so they are named."""
    assert _HOME_TREE is not None
    diagram = _HOME_TREE.group(1)

    for directory in (VERIFIERS_DIRECTORY, TASKSET_DIRECTORY, BUNDLE_DIRECTORY):
        assert f"{directory}/" in diagram, directory


def test_the_default_home_is_named_by_the_application_name_it_uses() -> None:
    """A reader has to be able to find the directory from the document alone."""
    assert f"/{APPLICATION_NAME}" in RUNBOOK
    assert "Library/Application Support" in RUNBOOK
    assert ".local/share" in RUNBOOK


# The headline: the signing key -------------------------------------------------------


def test_the_runbook_names_the_private_key_at_the_path_that_writes_it() -> None:
    """The one claim a reader must be able to act on without checking."""
    assert _HOME_TREE is not None
    identities = paths_from_root(Path("/techtree-home")).identities_dir.name

    assert f"{identities}/" in _HOME_TREE.group(1)
    assert PRIVATE_KEY_FILENAME in RUNBOOK
    assert PUBLIC_IDENTITY_FILENAME in RUNBOOK
    assert f"{identities}/{PRIVATE_KEY_FILENAME}" in RUNBOOK


def test_the_runbook_says_the_key_survives_an_uninstall_and_cannot_be_recovered() -> (
    None
):
    """Both halves of the warning, or it is not a warning."""
    collapsed = " ".join(RUNBOOK.split()).lower()

    assert "private signing key survives an uninstall" in collapsed
    assert "irreversible" in collapsed
    assert "no escrow, no backup, and no recovery" in collapsed


def test_the_private_key_is_not_something_the_package_manager_removes() -> None:
    """The uninstall section must not be read as removing the home."""
    section = RUNBOOK.split("## What `uv tool uninstall techtree` removes", 1)
    assert len(section) == 2, "the runbook has no uninstall section"
    body = " ".join(section[1].split("## ", 1)[0].split())

    assert "uv tool uninstall techtree" in body
    assert "It removes nothing else." in body
    assert "does not touch the Techtree home" in body


# The things outside the home ---------------------------------------------------------


def test_the_runbook_names_the_container_image_this_build_pins() -> None:
    """Read out of the catalog, so a re-pin fails here rather than misleading."""
    catalog = EmbeddedCatalogRepository(packaged_catalog_root())
    climb = catalog.load_climb("hello-world-climb@1")
    campaign = catalog.load_campaign(climb.campaign_spec_digest)

    assert campaign.subject.runtime.image in RUNBOOK
    assert f"docker image rm {campaign.subject.runtime.image}" in RUNBOOK


def test_the_runbook_names_the_shared_uv_state_it_does_not_delete() -> None:
    """Both survivors, and the reason Techtree leaves them alone."""
    collapsed = " ".join(RUNBOOK.split())

    assert "uv cache dir" in collapsed
    assert "uv cache clean" in collapsed
    assert "uv python uninstall" in collapsed
    assert "shared with everything else you use uv for" in collapsed


def test_the_runbook_says_techtree_never_pulls_or_deletes_the_image() -> None:
    """Techtree checks the daemon holds it and refuses otherwise; say that."""
    collapsed = " ".join(RUNBOOK.split()).lower()

    assert "never pulls that image and never deletes it" in collapsed


# There is no command for this, and the document must not imply one ------------------


def test_the_cli_really_has_no_purge_command() -> None:
    """The runbook says removal is a filesystem operation. Hold that true.

    Read off the built Typer application rather than a list here, so adding a
    command that deletes state without documenting it fails this test.
    """
    app = create_app()
    names = {group.name for group in app.registered_groups}
    names |= {command.name for command in app.registered_commands}

    forbidden = {"uninstall", "purge", "reset", "clean", "delete", "remove"}

    assert not (names & forbidden), f"a state-removing command exists: {names}"


def test_the_runbook_says_there_is_no_purge_command() -> None:
    assert "no `techtree uninstall` and no purge command" in RUNBOOK


def test_the_runbook_offers_the_relocation_option_the_cli_actually_has() -> None:
    """``--home`` is the only lever, and the document must not invent another."""
    from techtree.cli.app import GLOBAL_VALUE_OPTIONS

    assert "--home" in GLOBAL_VALUE_OPTIONS
    collapsed = " ".join(RUNBOOK.split())

    assert "--home PATH" in collapsed
    assert "there is no environment variable a user sets to relocate it" in collapsed


def test_the_removal_commands_target_the_directories_the_home_has() -> None:
    """Every ``rm -rf`` in the runbook points at real Techtree state.

    Read out of the document: a command that drifted to a stale path, or to a
    path outside the home, is caught rather than copied by a reader.
    """
    removals = re.findall(r'rm -rf "\$HOME/([^"]+)"', RUNBOOK)
    assert removals, "the runbook documents no removal command"

    members = _home_members()
    for target in removals:
        relative = target.removeprefix(f".local/share/{APPLICATION_NAME}").strip("/")
        assert target.startswith(f".local/share/{APPLICATION_NAME}"), target
        assert relative == "" or relative in members, target


# What it cannot promise. Decision 0013 -----------------------------------------------


def test_the_runbook_states_the_provider_boundary_rather_than_implying_it() -> None:
    """Decision 0013 s4: local retention is not the same claim as no retention."""
    collapsed = " ".join(RUNBOOK.split()).lower()

    assert "model inference" in collapsed
    assert "provider" in collapsed
    assert "cannot reach into your model provider" in collapsed


def test_the_runbook_admits_it_cannot_recall_a_copied_proof() -> None:
    collapsed = " ".join(RUNBOOK.split()).lower()

    assert "cannot find copies you made" in collapsed
