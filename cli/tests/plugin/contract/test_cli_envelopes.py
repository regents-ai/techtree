"""The plugin's envelope contract against the real Techtree CLI.

Specification sections 7.5 and 7.15, and the chief's instruction to verify the
committed CLI contract rather than assume it.

Two layers. The recorded envelopes in ``tests/fixtures/cli`` are exact bytes
captured from the installed CLI, so the contract is checked on every run,
everywhere. The live tests re-check the same commands against a CLI that is
actually present, which is what catches the day the two repositories drift.

A recorded envelope is never edited. Editing one turns a capture into an
assertion about what somebody expected the CLI to say, which is the one thing
these files exist not to be: they were re-captured at the ``techtree.cli.v2``
cutover, from Techtree homes created for the capture under ``/tmp``, and those
paths are in the bytes because the CLI put them there.

Capturing rather than editing puts one obligation on whoever captures: run the
CLI somewhere nobody's home directory can reach the bytes. ``doctor`` reports
the interpreter it runs on, the Techtree home it read, and the executables it
found, so it was captured from a virtualenv and a home under ``/tmp`` with a
neutral ``PATH`` and ``HOME``. The test at the end of this module holds the
whole fixture tree to that.

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
from techtree_hermes.cli.bridge import RELEASE_INFO_ARGUMENTS
from techtree_hermes.cli.constants import CLI_COMMAND, CLI_JSON_FLAGS
from techtree_hermes.cli.errors import CliEnvelopeError
from techtree_hermes.cli.release import compare_cli_release, load_embedded_release_core
from techtree_hermes.services.models import parse_cli_envelope

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "cli"
RECORDED = sorted(FIXTURES.glob("*.json"))

#: Every read-only command whose recorded output is checked here, and the
#: operation its envelope reports. All five read, so all five answer under
#: ``plan.inspect``.
#:
#: Whether a host can run a Climb changes the shape of the answer, so both
#: shapes are on record. Each comes from a throwaway Techtree home created for
#: the capture, so both stay reproducible instead of depending on what any one
#: machine happens to have installed on the day:
#:
#: * ``climb-list.json`` and ``climb-show.json`` come from an empty home, with
#:   no evaluation engine in it at all. Compatibility is false, and the issue
#:   is a blocking ``engine_not_installed`` error — which the envelope reports
#:   as a blocker rather than a warning.
#: * ``climb-list-compatible.json`` and ``climb-show-compatible.json`` come
#:   from the same home after ``techtree engine install``, with the
#:   installation record's ``verified`` flag cleared so the engine reads as
#:   installed but unverified. Compatibility is true, and the issue is a
#:   non-blocking ``engine_not_verified`` warning. Installing an engine and
#:   vouching for it are separate steps, so that state is one a person really
#:   reaches.
#:
#: The remaining envelopes are read-only answers that do not depend on which
#: engine a home holds, and are captured from the ordinary one.
#:
#: ``release-info.json`` reports a null ``source_commit`` and the warning that
#: goes with it, because it is captured from the source tree rather than from a
#: built wheel, and only a wheel is stamped with the commit it was built from
#: (Techtree decisions document 0026). The plugin accepts both shapes, because
#: it compares only the coordinates both documents hold; the wheel capture
#: comes back when there is a wheel carrying this release again.
#:
#: Everything else about the two Climb captures — the Climb, the Campaign, the
#: policy, the digests — is identical, which is the point: the plugin must
#: read both without either being a special case.
RECORDED_COMMANDS = {
    "doctor.json": "plan.inspect",
    "climb-list.json": "plan.inspect",
    "climb-list-compatible.json": "plan.inspect",
    "climb-show.json": "plan.inspect",
    "climb-show-compatible.json": "plan.inspect",
    "climb-show-not-found.json": "plan.inspect",
    "release-info.json": "plan.inspect",
    "release-verify.json": "plan.inspect",
}

#: The two recorded ``climb show`` shapes, and what each one says about a host.
#: The last element is whether the issue is blocking, which is also what
#: decides whether the envelope reports it as a blocker or as a warning.
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


def test_no_fixture_carries_a_path_out_of_somebodys_home() -> None:
    """A capture is committed, so where it was captured is committed with it.

    Doctor reports the interpreter it runs on and the executables it found, so
    a capture taken on a laptop names that laptop's owner. Nothing here needs
    a home directory, and a fixture that carried one would put a person's
    username in the repository for as long as the file lives.
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
def test_a_recorded_envelope_parses(path: Path) -> None:
    envelope = parse_cli_envelope(path.read_text(encoding="utf-8"))

    assert envelope["operation"] == RECORDED_COMMANDS[path.name]
    assert isinstance(envelope["ok"], bool)


@pytest.mark.parametrize("name", sorted(RECORDED_COMPATIBILITY))
def test_a_recorded_climb_reports_its_hosts_readiness(name: str) -> None:
    """Both readiness answers are one envelope shape, differing only in verdict."""
    compatible, status, code, blocking = RECORDED_COMPATIBILITY[name]
    envelope = parse_cli_envelope((FIXTURES / name).read_text(encoding="utf-8"))

    readiness = envelope["facts"]["climb"]["compatibility"]
    assert envelope["ok"] is True
    assert readiness["compatible"] is compatible
    assert readiness["engine_status"] == status
    assert readiness["issues"][0]["code"] == code
    assert readiness["issues"][0]["blocking"] is blocking

    # A blocking issue is a blocker, and it names what it stops; one that
    # blocks nothing is a warning. A caller must not have to read the payload's
    # own ``blocking`` flag to learn which.
    reported = envelope["blockers"] if blocking else envelope["warnings"]
    assert code in {entry["id"] for entry in reported}
    if blocking:
        assert envelope["blockers"][0]["blocks"] == ["plan.prepare", "action.execute"]


def test_the_two_recorded_climbs_differ_only_in_host_readiness() -> None:
    """A Climb is the same Climb whether or not this machine can run it."""
    blocked = parse_cli_envelope(
        (FIXTURES / "climb-show.json").read_text(encoding="utf-8")
    )["facts"]["climb"]
    ready = parse_cli_envelope(
        (FIXTURES / "climb-show-compatible.json").read_text(encoding="utf-8")
    )["facts"]["climb"]

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
    assert "retryable" not in envelope["error"]
    action = envelope["next_actions"][0]
    assert action["operation"] == "plan.inspect"
    assert action["prepared_arguments"]["command"] == ["climb", "list"]
    assert action["retry_class"] == "safe"


def test_the_recorded_release_belongs_to_the_same_release_as_this_plugin() -> None:
    """The plugin and the CLI must carry the same ReleaseCore bytes."""
    envelope = parse_cli_envelope(
        (FIXTURES / "release-info.json").read_text(encoding="utf-8")
    )

    assert compare_cli_release(load_embedded_release_core(), envelope["facts"]) == []


def test_the_recorded_release_verification_passed() -> None:
    envelope = parse_cli_envelope(
        (FIXTURES / "release-verify.json").read_text(encoding="utf-8")
    )

    assert envelope["facts"]["verified"] is True
    assert (
        envelope["facts"]["release_core_digest"]
        == (
            json.loads((FIXTURES / "release-info.json").read_text(encoding="utf-8"))[
                "facts"
            ]["release_core_digest"]
        )
    )


# The installed CLI -----------------------------------------------------------------


@pytest.mark.real_cli
@REQUIRES_CLI
def test_doctor_returns_one_envelope_this_plugin_accepts() -> None:
    completed = _run("doctor", *CLI_JSON_FLAGS)

    envelope = parse_cli_envelope(completed.stdout)

    assert envelope["operation"] == "plan.inspect"
    assert isinstance(envelope["facts"]["checks"], list)


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
    mismatches = compare_cli_release(load_embedded_release_core(), envelope["facts"])

    assert envelope["ok"] is True
    assert mismatches == []


@pytest.mark.real_cli
@REQUIRES_CLI
def test_the_installed_release_verifies_against_its_own_coordinates() -> None:
    completed = _run("release", "verify", *CLI_JSON_FLAGS)

    envelope = parse_cli_envelope(completed.stdout)

    assert envelope["facts"]["verified"] is True
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
