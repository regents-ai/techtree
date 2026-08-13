"""The plugin's envelope contract against the real Techtree CLI.

Specification sections 7.5 and 7.15, and the chief's instruction to verify the
committed CLI contract rather than assume it.

Only read-only commands run here, and only when a CLI is available. Point
``TECHTREE_CLI_ARGV`` at one to run these against a checkout that is not on
PATH, for example::

    TECHTREE_CLI_ARGV='uv run --project ../techtree-python techtree' \\
        uv run pytest tests/contract/test_cli_envelopes.py
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess

import pytest
from techtree_hermes.constants import CLI_COMMAND, CLI_JSON_FLAGS
from techtree_hermes.errors import CliEnvelopeError
from techtree_hermes.models import parse_cli_envelope

pytestmark = pytest.mark.real_cli


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


@REQUIRES_CLI
def test_doctor_returns_one_envelope_this_plugin_accepts() -> None:
    completed = _run("doctor", *CLI_JSON_FLAGS)

    envelope = parse_cli_envelope(completed.stdout)

    assert envelope["command"] == "doctor"
    assert isinstance(envelope["data"]["checks"], list)


@REQUIRES_CLI
def test_the_climb_list_envelope_is_accepted() -> None:
    completed = _run("climb", "list", *CLI_JSON_FLAGS)

    envelope = parse_cli_envelope(completed.stdout)

    assert envelope["ok"] is True


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
