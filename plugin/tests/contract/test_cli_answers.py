"""The plugin's answer contract against the real ``regents techtree``.

Specification sections 7.5 and 7.15, and regents-cli's
``docs/techtree-plugin.md``, which lists every call the plugin makes and the
answer each one gives.

Two layers. The recorded answers in ``tests/fixtures/cli`` are exact bytes
captured from regents, so the contract is checked on every run, everywhere.
The live tests re-check the same commands against the regents-cli that
``REGENTS_CLI_ARGV`` names, which is what catches the day the two repositories drift.

A recorded answer is never edited. Editing one turns a capture into an
assertion about what somebody expected regents to say, which is the one thing
these files exist not to be. They were captured from regents-cli 1.0.0 with an
empty home created for the capture, so the Climb reads as one whose evaluation
engine is not installed yet. ``doctor`` is not recorded: it reports the
interpreter it runs on and the Techtree home it read, which are paths out of
whoever captured it. The live test below checks it instead.

Only read-only commands appear here. Nothing prepares a draft, starts a run,
spends model budget, or writes to a Techtree home.
"""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

import pytest
from techtree_hermes.cli.bridge import RELEASE_INFO_ARGUMENTS
from techtree_hermes.cli.constants import CLI_COMMAND, CLI_JSON_FLAGS, CLI_NAMESPACE
from techtree_hermes.cli.errors import CliAnswerError
from techtree_hermes.cli.release import compare_cli_release, load_embedded_release_core
from techtree_hermes.services.models import parse_cli_answer

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "cli"
RECORDED = sorted(FIXTURES.glob("*.json"))

#: Every recorded read-only command, and the error code it answers with, or
#: None for a success.
RECORDED_COMMANDS: dict[str, str | None] = {
    "climb-list.json": None,
    "climb-show.json": None,
    "climb-show-not-found.json": "climb_not_found",
    "release-info.json": None,
    "release-verify.json": None,
    "run-status-not-found.json": "run_not_found",
}


def _cli_argv() -> list[str] | None:
    configured = os.environ.get("REGENTS_CLI_ARGV")
    return shlex.split(configured) if configured else None


#: Named rather than found on PATH: another program can be installed as
#: ``regents``, and these tests are about regents-cli.
REQUIRES_CLI = pytest.mark.skipif(
    _cli_argv() is None,
    reason="REGENTS_CLI_ARGV does not name a regents-cli to ask",
)


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    argv = _cli_argv()
    assert argv is not None
    return subprocess.run(
        [*argv, *CLI_NAMESPACE, *arguments, *CLI_JSON_FLAGS],
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )


def _recorded(name: str) -> dict[str, object]:
    return parse_cli_answer((FIXTURES / name).read_text(encoding="utf-8"))


# Recorded answers -----------------------------------------------------------------


def test_every_recorded_command_is_covered() -> None:
    assert {path.name for path in RECORDED} == set(RECORDED_COMMANDS)


def test_no_fixture_carries_a_path_out_of_somebodys_home() -> None:
    """A capture is committed, so where it was captured is committed with it.

    A fixture that carried a home directory would put a person's username in
    the repository for as long as the file lives.
    """
    home_directories = ("/Users/", "/home/")
    for path in sorted((FIXTURES.parent).rglob("*")):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for directory in home_directories:
            assert directory not in text, (
                f"{path.relative_to(FIXTURES.parent)} names {directory}, which "
                "is a path out of whoever captured it"
            )


@pytest.mark.parametrize("path", RECORDED, ids=lambda path: path.name)
def test_a_recorded_answer_parses(path: Path) -> None:
    answer = parse_cli_answer(path.read_text(encoding="utf-8"))

    code = RECORDED_COMMANDS[path.name]
    if code is None:
        assert "error" not in answer
        assert isinstance(answer["report"], str)
    else:
        assert set(answer) == {"error"}
        assert answer["error"]["code"] == code


def test_a_recorded_climb_reports_its_hosts_readiness() -> None:
    """An empty home has no engine, and the Climb says so rather than failing."""
    readiness = _recorded("climb-show.json")["climb"]["compatibility"]  # type: ignore[index]

    assert readiness["compatible"] is False
    assert readiness["engine_status"] == "not_installed"
    assert readiness["issues"][0]["code"] == "engine_not_installed"


def test_a_recorded_failure_carries_a_typed_error() -> None:
    error = _recorded("climb-show-not-found.json")["error"]

    assert error["code"] == "climb_not_found"  # type: ignore[index]
    assert error["details"]["reference"] == "does-not-exist@1"  # type: ignore[index]


def test_the_recorded_release_belongs_to_the_same_release_as_this_plugin() -> None:
    """The plugin and regents must carry the same ReleaseCore bytes."""
    answer = _recorded("release-info.json")

    assert compare_cli_release(load_embedded_release_core(), answer) == []


def test_the_recorded_release_verification_passed() -> None:
    verified = _recorded("release-verify.json")

    assert verified["verified"] is True
    assert (
        verified["release_core_digest"]
        == _recorded("release-info.json")["release_core_digest"]
    )


# The installed regents -------------------------------------------------------------


@pytest.mark.real_cli
@REQUIRES_CLI
def test_doctor_returns_one_answer_this_plugin_accepts() -> None:
    completed = _run("doctor")

    answer = parse_cli_answer(completed.stdout)

    if completed.returncode == 0:
        assert isinstance(answer["checks"], list)
        assert answer["blocking_failures"] == []
    else:
        assert answer["error"]["code"] == "environment_not_ready"
        assert answer["error"]["details"]["blocking_failures"]


@pytest.mark.real_cli
@REQUIRES_CLI
def test_the_climb_list_answer_is_accepted() -> None:
    completed = _run("climb", "list")

    answer = parse_cli_answer(completed.stdout)

    assert completed.returncode == 0
    assert answer["count"] == len(answer["climbs"])


@pytest.mark.real_cli
@REQUIRES_CLI
def test_the_installed_regents_belongs_to_this_plugins_release() -> None:
    """The cross-repository check the release depends on, run for real."""
    completed = _run(*RELEASE_INFO_ARGUMENTS)

    answer = parse_cli_answer(completed.stdout)

    assert completed.returncode == 0
    assert compare_cli_release(load_embedded_release_core(), answer) == []


@pytest.mark.real_cli
@REQUIRES_CLI
def test_a_read_only_failure_is_reported_in_band() -> None:
    """A failing command still answers with one JSON object and an exit code."""
    completed = _run("climb", "show", "does-not-exist@1")

    answer = parse_cli_answer(completed.stdout)

    assert completed.returncode == 4
    assert answer["error"]["code"] == "climb_not_found"


@pytest.mark.real_cli
@REQUIRES_CLI
def test_a_missing_run_is_not_found() -> None:
    completed = _run("run", "status", "run_" + "0" * 32)

    answer = parse_cli_answer(completed.stdout)

    assert completed.returncode == 4
    assert answer["error"]["code"] == "run_not_found"


@pytest.mark.real_cli
@REQUIRES_CLI
def test_the_version_flag_answers_outside_the_answer_contract() -> None:
    """`regents --version` prints one plain line, so the plugin must not parse it.

    This is the one read-only call whose output is not a JSON answer. Recording
    it here keeps a later change from bridging it by mistake.
    """
    argv = _cli_argv()
    assert argv is not None
    completed = subprocess.run(
        [*argv, "--version"], capture_output=True, text=True, check=False, timeout=60
    )

    assert completed.returncode == 0
    assert completed.stdout.split()[0] == CLI_COMMAND
    with pytest.raises(CliAnswerError):
        parse_cli_answer(completed.stdout)
