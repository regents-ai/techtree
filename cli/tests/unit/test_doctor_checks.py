"""What Doctor says about the host agent, and what it refuses to claim.

Two checks here are about Hermes rather than about Techtree, and both are
observations with a next step attached. A machine with no Hermes and no plugin
runs every command in this program, so neither check may block, neither may
fail, and neither may turn a ready host into an unready one. Every test below
holds that alongside whatever else it is checking.

The probes are driven with a stand-in ``hermes`` on PATH rather than by
patching over the subprocess call, because the thing worth testing is the whole
probe: that the argument vector is one a real Hermes answers, that a Hermes
which answers with something else is read as unknown, and that a slow one is
given up on. A patched ``_probe`` would test the branch table and nothing
underneath it.

One claim is absent on purpose and is guarded here as an absence. Doctor cannot
name the commit the plugin is pinned at: decision 0026 makes the release
contract a document authored before the plugin that embeds it, and the plugin's
commit is written down a step later still, by the website's release document.
The address of the page that knows is therefore the whole of what Doctor may
offer, and a coordinate appearing in this copy would mean somebody invented
one.
"""

from __future__ import annotations

import re
import stat
from pathlib import Path
from typing import Final

import pytest

from techtree.doctor import checks as doctor_checks
from techtree.doctor.checks import (
    START_PAGE_URL,
    check_hermes_cli,
    check_hermes_plugin,
)
from techtree.models.cli import CheckStatus

#: A plugin listing carrying the plugin, in the shape Hermes documents.
INSTALLED_LISTING: Final = (
    '[{"name": "browser-firecrawl", "status": "not enabled"}, '
    '{"name": "techtree", "status": "enabled", "version": "0.1.0"}]'
)

#: The same answer from a Hermes that does not have it.
WITHOUT_LISTING: Final = '[{"name": "browser-firecrawl", "status": "not enabled"}]'


def _standin_hermes(directory: Path, script: str) -> None:
    """Put an executable ``hermes`` in ``directory`` that behaves as told."""
    executable = directory / "hermes"
    executable.write_text(f"#!/bin/sh\n{script}\n", encoding="utf-8")
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR)


def _answering(listing: str) -> str:
    """A stand-in that reports a version and prints ``listing`` for a listing."""
    return "\n".join(
        (
            'if [ "$1" = "--version" ]; then',
            '  echo "Hermes Agent v0.20.5"',
            "  exit 0",
            "fi",
            'if [ "$1" = "plugins" ]; then',
            f"  printf '%s\\n' '{listing}'",
            "  exit 0",
            "fi",
            "exit 1",
        )
    )


@pytest.fixture
def host_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Make ``tmp_path`` the only directory Doctor's probes can look in.

    It starts empty, which is the host that has no Hermes at all. A test that
    wants one puts it there. The two system directories are on the end because
    a stand-in written in shell needs the ordinary utilities, and neither of
    them is anywhere a Hermes is installed.
    """
    monkeypatch.setenv("PATH", f"{tmp_path}:/usr/bin:/bin")
    return tmp_path


# Nothing here is ever a fault -------------------------------------------------------


def test_no_host_agent_check_can_block_or_fail(host_path: Path) -> None:
    """The point of the pair: a host without either is still a ready host."""
    without_hermes = [check_hermes_cli(), check_hermes_plugin()]

    _standin_hermes(host_path, _answering(WITHOUT_LISTING))
    without_plugin = [check_hermes_cli(), check_hermes_plugin()]

    _standin_hermes(host_path, _answering(INSTALLED_LISTING))
    with_both = [check_hermes_cli(), check_hermes_plugin()]

    for check in [*without_hermes, *without_plugin, *with_both]:
        assert check.blocking is False, check
        assert check.status is not CheckStatus.FAIL, check


# Hermes itself ----------------------------------------------------------------------


def test_a_missing_hermes_says_where_techtree_is_driven_from(host_path: Path) -> None:
    check = check_hermes_cli()

    assert check.status is CheckStatus.WARN
    assert "runs inside Hermes" in check.detail
    assert START_PAGE_URL in check.detail


def test_a_present_hermes_reports_its_version_and_gives_no_advice(
    host_path: Path,
) -> None:
    _standin_hermes(host_path, _answering(INSTALLED_LISTING))

    check = check_hermes_cli()

    assert check.status is CheckStatus.PASS
    assert check.detail == "Hermes Agent v0.20.5"
    assert START_PAGE_URL not in check.detail


# The plugin -------------------------------------------------------------------------


def test_the_plugin_check_is_skipped_when_there_is_no_hermes(host_path: Path) -> None:
    """Nothing can be said about the plugins of a Hermes that is not there."""
    check = check_hermes_plugin()

    assert check.status is CheckStatus.SKIP
    assert "hermes executable was not found" in check.detail


def test_an_installed_plugin_is_reported_without_advice(host_path: Path) -> None:
    _standin_hermes(host_path, _answering(INSTALLED_LISTING))

    check = check_hermes_plugin()

    assert check.status is CheckStatus.PASS
    assert check.detail == "The Techtree plugin is installed for this Hermes"
    assert START_PAGE_URL not in check.detail
    assert check.metadata["installed"] is True


def test_a_missing_plugin_is_a_next_step_and_points_at_the_start_page(
    host_path: Path,
) -> None:
    _standin_hermes(host_path, _answering(WITHOUT_LISTING))

    check = check_hermes_plugin()

    assert check.status is CheckStatus.WARN
    assert check.blocking is False
    assert "is not installed for this Hermes" in check.detail
    assert "works without it" in check.detail
    assert START_PAGE_URL in check.detail
    assert check.metadata["installed"] is False


def test_a_hermes_with_no_plugins_at_all_is_still_a_readable_answer(
    host_path: Path,
) -> None:
    """An empty listing is an answer, and the answer is that it is not there."""
    _standin_hermes(host_path, _answering("[]"))

    assert check_hermes_plugin().status is CheckStatus.WARN


def test_the_probe_asks_hermes_for_a_machine_readable_listing(
    host_path: Path,
) -> None:
    """The argument vector is part of the contract, so it is asserted."""
    recorded = host_path / "argv"
    _standin_hermes(
        host_path,
        f'printf "%s\\n" "$@" > "{recorded}"\necho "[]"\nexit 0',
    )

    check_hermes_plugin()

    assert recorded.read_text(encoding="utf-8").split() == ["plugins", "list", "--json"]


# What Doctor declines to claim ------------------------------------------------------


#: Every way a Hermes can answer without answering the question.
UNREADABLE_ANSWERS: Final[tuple[tuple[str, str], ...]] = (
    (
        "a Hermes too old to know the flag",
        'echo "unrecognized arguments: --json" >&2\nexit 2',
    ),
    ("a Hermes that answers with a table", 'echo "Plugins"\nexit 0'),
    ("a Hermes that answers with an object", "echo '{}'\nexit 0"),
    ("a Hermes that answers with nothing", "exit 0"),
    (
        "a listing whose entries are not named plugins",
        'echo \'[{"plugin": "techtree"}]\'\nexit 0',
    ),
)


@pytest.mark.parametrize(
    ("described", "script"),
    UNREADABLE_ANSWERS,
    ids=[described for described, _ in UNREADABLE_ANSWERS],
)
def test_an_unreadable_answer_is_reported_as_unknown_not_as_absence(
    host_path: Path, described: str, script: str
) -> None:
    """An absence nobody observed must never be reported as one.

    Telling somebody to install a plugin they already have is the specific
    mistake this branch exists to avoid, so every way of failing to read an
    answer lands on the same reticent sentence.
    """
    _standin_hermes(host_path, script)

    check = check_hermes_plugin()

    assert check.status is CheckStatus.SKIP, described
    assert "did not return a plugin list this build can read" in check.detail
    assert START_PAGE_URL not in check.detail


def test_a_hermes_that_does_not_answer_in_time_is_given_up_on(
    host_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A slow probe says less rather than waiting, and says which it was."""
    monkeypatch.setattr(doctor_checks, "VERSION_TIMEOUT_SECONDS", 0.2)
    _standin_hermes(host_path, "sleep 5")

    check = check_hermes_plugin()

    assert check.status is CheckStatus.SKIP
    assert check.metadata["timed_out"] is True


# The coordinate that does not exist here --------------------------------------------


#: Anything that would be a pinned plugin coordinate: a git revision, an
#: install command, a repository reference, or a pinned version.
INVENTED_COORDINATE: Final = re.compile(
    r"\b[0-9a-f]{7,40}\b|\bplugins\s+install\b|\bgithub\.com\b|@v?\d+\.\d+",
    re.I,
)


def test_the_doctor_never_names_a_pinned_plugin_coordinate(host_path: Path) -> None:
    """Decision 0026's ordering, stated as the sentence Doctor may not write.

    The contract is authored first, the plugin embeds it, and only then is the
    plugin's commit written down — by the website, not by anything shipped
    here. Doctor has no coordinate to give, so the guard is against one
    appearing anyway.
    """
    details = [check_hermes_cli().detail, check_hermes_plugin().detail]
    _standin_hermes(host_path, _answering(WITHOUT_LISTING))
    details += [check_hermes_cli().detail, check_hermes_plugin().detail]

    for detail in details:
        assert not INVENTED_COORDINATE.search(detail), detail
