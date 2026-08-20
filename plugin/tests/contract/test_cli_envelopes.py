"""The plugin's envelope contract against the real Techtree CLI.

Specification sections 7.5 and 7.15, and the chief's instruction to verify the
committed CLI contract rather than assume it.

Two layers. The recorded envelopes in ``tests/fixtures/cli`` are exact bytes
captured from the installed CLI, so the contract is checked on every run,
everywhere. The live tests re-check the same commands against a CLI that is
actually present, which is what catches the day the two repositories drift.

Only read-only commands appear here. Nothing prepares a draft, starts a run,
spends model budget, or writes to a Techtree home.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest
from techtree_hermes.bridge import RELEASE_INFO_ARGUMENTS
from techtree_hermes.constants import CLI_COMMAND, CLI_JSON_FLAGS
from techtree_hermes.errors import CliEnvelopeError
from techtree_hermes.models import parse_cli_envelope
from techtree_hermes.release import compare_cli_release, load_embedded_release_core

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "cli"
RECORDED = sorted(FIXTURES.glob("*.json"))

#: Every read-only command whose recorded output is checked here, and the
#: command name its envelope reports.
#:
#: Whether a host can run a Climb changes the shape of the answer, so both
#: shapes are on record. Each comes from a throwaway Techtree home created for
#: the capture, so both stay reproducible instead of depending on what any one
#: machine happens to have installed on the day:
#:
#: * ``climb-list.json`` and ``climb-show.json`` come from an empty home, with
#:   no evaluation engine in it at all. Compatibility is false, and the issue
#:   is a blocking ``engine_not_installed`` error.
#: * ``climb-list-compatible.json`` and ``climb-show-compatible.json`` come
#:   from a home with the release's own engine unpacked into it.
#:   Compatibility is true, and the issue is a non-blocking
#:   ``engine_not_verified`` warning. The engine reads as installed but
#:   unverified because installing it and vouching for it are separate steps.
#:
#: The remaining envelopes are read-only answers that do not depend on which
#: engine a home holds, and are captured from the ordinary one.
#:
#: ``release-info.json`` reports a null ``source_commit`` and the warning that
#: goes with it. It used to carry a real one, because it was captured from the
#: candidate wheel installed into an isolated home and a wheel is stamped with
#: the commit it was built from (Techtree decisions document 0026). The
#: Techtree decision 0029 regeneration moved the catalog and the ReleaseCore
#: ahead of any wheel, so these two were re-captured from the source tree,
#: where the CLI reports null and says so. The plugin accepts both shapes,
#: because it compares only the coordinates both documents hold; the wheel
#: capture comes back when there is a wheel carrying this release again.
#:
#: Everything else about the two Climb captures — the Climb, the Campaign, the
#: policy, the digests — is identical, which is the point: the plugin must
#: read both without either being a special case.
RECORDED_COMMANDS = {
    "doctor.json": "doctor",
    "climb-list.json": "climb list",
    "climb-list-compatible.json": "climb list",
    "climb-show.json": "climb show",
    "climb-show-compatible.json": "climb show",
    "climb-show-not-found.json": "climb show",
    "release-info.json": "release info",
    "release-verify.json": "release verify",
}

#: The two recorded ``climb show`` shapes, and what each one says about a host.
RECORDED_COMPATIBILITY = {
    "climb-show.json": (False, "not_installed", "engine_not_installed", True),
    "climb-show-compatible.json": (
        True,
        "installed_unverified",
        "engine_not_verified",
        False,
    ),
}


def _cli_argv() -> list[str] | None:
    configured = os.environ.get("TECHTREE_CLI_ARGV")
    if configured:
        return shlex.split(configured)
    located = shutil.which(CLI_COMMAND)
    return [located] if located else None


REQUIRES_CLI = pytest.mark.skipif(
    _cli_argv() is None,
    reason="no Techtree CLI on PATH and TECHTREE_CLI_ARGV is not set",
)


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    argv = _cli_argv()
    assert argv is not None
    return subprocess.run(
        [*argv, *arguments],
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )


# Recorded envelopes ---------------------------------------------------------------


def test_every_recorded_command_is_covered() -> None:
    assert {path.name for path in RECORDED} == set(RECORDED_COMMANDS)


@pytest.mark.parametrize("path", RECORDED, ids=lambda path: path.name)
def test_a_recorded_envelope_parses(path: Path) -> None:
    envelope = parse_cli_envelope(path.read_text(encoding="utf-8"))

    assert envelope["command"] == RECORDED_COMMANDS[path.name]
    assert isinstance(envelope["ok"], bool)


@pytest.mark.parametrize("name", sorted(RECORDED_COMPATIBILITY))
def test_a_recorded_climb_reports_its_hosts_readiness(name: str) -> None:
    """Both readiness answers are one envelope shape, differing only in verdict."""
    compatible, status, code, blocking = RECORDED_COMPATIBILITY[name]
    envelope = parse_cli_envelope((FIXTURES / name).read_text(encoding="utf-8"))

    readiness = envelope["data"]["climb"]["compatibility"]
    assert envelope["ok"] is True
    assert readiness["compatible"] is compatible
    assert readiness["engine_status"] == status
    assert readiness["issues"][0]["code"] == code
    assert readiness["issues"][0]["blocking"] is blocking


def test_the_two_recorded_climbs_differ_only_in_host_readiness() -> None:
    """A Climb is the same Climb whether or not this machine can run it."""
    blocked = parse_cli_envelope(
        (FIXTURES / "climb-show.json").read_text(encoding="utf-8")
    )["data"]["climb"]
    ready = parse_cli_envelope(
        (FIXTURES / "climb-show-compatible.json").read_text(encoding="utf-8")
    )["data"]["climb"]

    assert blocked["reference"] == ready["reference"] == "hello-world-climb@1"
    assert blocked["title"] == ready["title"] == "Techtree Hello World"
    for pinned in ("campaign_spec_digest", "climb_digest", "task_count"):
        assert blocked[pinned] == ready[pinned]
    assert (
        blocked["compatibility"]["required_engine_digest"]
        == ready["compatibility"]["required_engine_digest"]
    )
    del blocked["compatibility"], ready["compatibility"]
    assert blocked == ready


def test_a_recorded_failure_carries_a_typed_error() -> None:
    envelope = parse_cli_envelope(
        (FIXTURES / "climb-show-not-found.json").read_text(encoding="utf-8")
    )

    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "climb_not_found"
    assert envelope["error"]["retryable"] is False
    assert envelope["next_actions"][0]["cli"][:2] == ["techtree", "climb"]


def test_the_recorded_release_belongs_to_the_same_release_as_this_plugin() -> None:
    """The plugin and the CLI must carry the same ReleaseCore bytes."""
    envelope = parse_cli_envelope(
        (FIXTURES / "release-info.json").read_text(encoding="utf-8")
    )

    assert compare_cli_release(load_embedded_release_core(), envelope["data"]) == []


def test_the_recorded_release_verification_passed() -> None:
    envelope = parse_cli_envelope(
        (FIXTURES / "release-verify.json").read_text(encoding="utf-8")
    )

    assert envelope["data"]["verified"] is True
    assert (
        envelope["data"]["release_core_digest"]
        == (
            json.loads((FIXTURES / "release-info.json").read_text(encoding="utf-8"))[
                "data"
            ]["release_core_digest"]
        )
    )


# The installed CLI -----------------------------------------------------------------


@pytest.mark.real_cli
@REQUIRES_CLI
def test_doctor_returns_one_envelope_this_plugin_accepts() -> None:
    completed = _run("doctor", *CLI_JSON_FLAGS)

    envelope = parse_cli_envelope(completed.stdout)

    assert envelope["command"] == "doctor"
    assert isinstance(envelope["data"]["checks"], list)


@pytest.mark.real_cli
@REQUIRES_CLI
def test_the_climb_list_envelope_is_accepted() -> None:
    completed = _run("climb", "list", *CLI_JSON_FLAGS)

    envelope = parse_cli_envelope(completed.stdout)

    assert envelope["ok"] is True


@pytest.mark.real_cli
@REQUIRES_CLI
def test_the_installed_cli_belongs_to_this_plugins_release() -> None:
    """The cross-repository check the release depends on, run for real."""
    completed = _run(*RELEASE_INFO_ARGUMENTS, *CLI_JSON_FLAGS)

    envelope = parse_cli_envelope(completed.stdout)
    mismatches = compare_cli_release(load_embedded_release_core(), envelope["data"])

    assert envelope["ok"] is True
    assert mismatches == []


@pytest.mark.real_cli
@REQUIRES_CLI
def test_the_installed_release_verifies_against_its_own_coordinates() -> None:
    completed = _run("release", "verify", *CLI_JSON_FLAGS)

    envelope = parse_cli_envelope(completed.stdout)

    assert envelope["data"]["verified"] is True
    assert completed.returncode == 0


@pytest.mark.real_cli
@REQUIRES_CLI
def test_a_read_only_failure_is_reported_in_band() -> None:
    """A failing command still answers with one envelope and an exit code."""
    completed = _run("climb", "show", "does-not-exist@1", *CLI_JSON_FLAGS)

    envelope = parse_cli_envelope(completed.stdout)

    assert completed.returncode != 0
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "climb_not_found"


@pytest.mark.real_cli
@REQUIRES_CLI
def test_the_version_flag_answers_outside_the_envelope_contract() -> None:
    """`--version` prints a bare version, so the plugin must not parse it.

    This is the one read-only call whose output is not an envelope. Recording
    it here keeps a later work package from bridging it by mistake.
    """
    completed = _run("--version", *CLI_JSON_FLAGS)

    assert completed.returncode == 0
    assert completed.stdout.strip()
    with pytest.raises(CliEnvelopeError):
        parse_cli_envelope(completed.stdout)
