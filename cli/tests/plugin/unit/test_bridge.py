"""The CLI bridge. Specification sections 7.5 and 7.15, bridge tests.

These run a real executable named ``techtree`` on a temporary PATH rather than
patching ``subprocess``, because the claims being tested are about the process
the bridge actually starts: its argv, its flags, the absence of a shell, and
what it does with whatever comes back.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from support import FakeCli, install_fake_cli, print_envelope
from techtree_hermes.bridge import (
    build_cli_argv,
    call_cli,
    invoke_cli,
    resolve_techtree_binary,
    verify_cli_release,
)
from techtree_hermes.constants import CLI_JSON_FLAGS
from techtree_hermes.errors import (
    CliEnvelopeError,
    CliInvocationError,
    CliNotInstalledError,
)
from techtree_hermes.release import load_embedded_release_core, release_core_digest


@pytest.fixture
def fake_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeCli:
    """A CLI that answers every call with one valid envelope."""
    return install_fake_cli(
        tmp_path / "bin", body=print_envelope(), monkeypatch=monkeypatch
    )


def _fake_cli_printing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str
) -> FakeCli:
    return install_fake_cli(tmp_path / "bin", body=body, monkeypatch=monkeypatch)


# Resolving the executable -------------------------------------------------------


def test_no_cli_on_path_is_reported_not_guessed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PATH", "")

    assert resolve_techtree_binary() is None
    with pytest.raises(CliNotInstalledError):
        build_cli_argv(["doctor"])


def test_only_the_one_executable_name_is_ever_resolved(fake_cli: FakeCli) -> None:
    located = resolve_techtree_binary()

    assert located is not None
    assert Path(located).name == "techtree"


# Building argv ------------------------------------------------------------------


def test_machine_flags_are_appended_exactly_once(fake_cli: FakeCli) -> None:
    argv = build_cli_argv(["climb", "list"])

    assert argv[1:3] == ["climb", "list"]
    for flag in CLI_JSON_FLAGS:
        assert argv.count(flag) == 1
    assert argv[-len(CLI_JSON_FLAGS) :] == list(CLI_JSON_FLAGS)


def test_a_caller_cannot_supply_the_machine_flags(fake_cli: FakeCli) -> None:
    with pytest.raises(CliInvocationError, match="added by the bridge"):
        build_cli_argv(["doctor", "--json"])


@pytest.mark.parametrize("argument", ["", "climb\x00list"])
def test_an_unusable_argument_never_reaches_a_process(
    fake_cli: FakeCli, argument: str
) -> None:
    with pytest.raises(CliInvocationError):
        build_cli_argv([argument])


def test_arguments_are_passed_as_literals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A shell metacharacter is an argument, not an instruction."""
    cli = _fake_cli_printing(tmp_path, monkeypatch, print_envelope())
    hostile = "procedure-transfer-dev@1; rm -rf ~"

    invoke_cli(["climb", "show", hostile])

    assert cli.recorded_argv()[0][2] == hostile


def test_the_call_runs_without_a_shell(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A shell would have expanded this; the CLI receives it untouched."""
    cli = _fake_cli_printing(tmp_path, monkeypatch, print_envelope())

    invoke_cli(["climb", "show", "$HOME"])

    assert cli.recorded_argv()[0][2] == "$HOME"


# Reading the answer --------------------------------------------------------------


def test_one_envelope_is_accepted_and_returned_unchanged(fake_cli: FakeCli) -> None:
    envelope = invoke_cli(["doctor"])

    assert envelope["command"] == "doctor"
    assert envelope["ok"] is True
    assert envelope["data"] == {"checks": []}


def test_two_json_records_are_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_cli_printing(
        tmp_path,
        monkeypatch,
        print_envelope() + "\n" + print_envelope(),
    )

    with pytest.raises(CliEnvelopeError, match="exactly one JSON document"):
        invoke_cli(["doctor"])


def test_ansi_in_machine_output_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_cli_printing(
        tmp_path,
        monkeypatch,
        "sys.stdout.write('\\x1b[32m' + json.dumps("
        + repr(
            {
                "schema_version": "techtree.cli.v1",
                "command": "doctor",
                "ok": True,
                "data": None,
                "error": None,
                "messages": [],
                "warnings": [],
                "next_actions": [],
            }
        )
        + ") + '\\x1b[0m')",
    )

    with pytest.raises(CliEnvelopeError, match="ANSI"):
        invoke_cli(["doctor"])


def test_oversized_output_is_refused_safely(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_cli_printing(tmp_path, monkeypatch, "print('x' * 100000)")

    with pytest.raises(CliEnvelopeError, match="more than the") as raised:
        invoke_cli(["doctor"], maximum_stdout_bytes=1024)

    assert raised.value.code == "cli_output_too_large"


def test_a_command_that_times_out_is_retryable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_cli_printing(tmp_path, monkeypatch, "import time; time.sleep(5)")

    with pytest.raises(CliInvocationError, match="did not finish") as raised:
        invoke_cli(["run", "status", "run_" + "0" * 32], timeout_seconds=0.5)

    assert raised.value.retryable is True


def test_a_failing_command_returns_its_own_envelope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Techtree reports its failures in-band; the bridge does not reword them."""
    failure = {
        "schema_version": "techtree.cli.v1",
        "command": "climb show",
        "ok": False,
        "data": None,
        "error": {
            "code": "climb_not_found",
            "message": "this build ships no Climb called 'nope@1'",
            "retryable": False,
            "details": {"reference": "nope@1"},
        },
        "messages": [],
        "warnings": [],
        "next_actions": [],
    }
    _fake_cli_printing(
        tmp_path,
        monkeypatch,
        f"print(json.dumps({failure!r}))\nsys.exit(5)",
    )

    response = call_cli(["climb", "show", "nope@1"])

    assert response.exit_code == 5
    assert response.ok is False
    assert response.envelope["error"]["code"] == "climb_not_found"


# Diagnostics ---------------------------------------------------------------------


def test_stderr_is_scrubbed_of_bearer_tokens_and_quoted_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    noisy = (
        "warning: Authorization: Bearer abc123DEF456ghi789 rejected; "
        'config was {"api_key": "sk-live-abcdefghijklmnop"}'
    )
    _fake_cli_printing(
        tmp_path,
        monkeypatch,
        print_envelope() + f"\nsys.stderr.write({noisy!r})",
    )

    response = call_cli(["doctor"])

    assert "abc123DEF456ghi789" not in response.stderr_excerpt
    assert "sk-live-abcdefghijklmnop" not in response.stderr_excerpt
    assert "redacted" in response.stderr_excerpt


def test_stderr_is_bounded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_cli_printing(
        tmp_path,
        monkeypatch,
        print_envelope() + "\nsys.stderr.write('noise ' * 20000)",
    )

    response = call_cli(["doctor"])

    assert len(response.stderr_excerpt) <= 2100


def test_provider_credentials_never_enter_the_invocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The environment is inherited, never read into arguments or diagnostics."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-live-must-never-appear")
    cli = _fake_cli_printing(
        tmp_path,
        monkeypatch,
        print_envelope()
        + "\nsys.stderr.write('using key ' + os.environ.get('OPENAI_API_KEY', ''))",
    )

    response = call_cli(["doctor"])

    assert "sk-live-must-never-appear" not in json.dumps(cli.recorded_argv())
    assert "sk-live-must-never-appear" not in response.stderr_excerpt
    assert "sk-live-must-never-appear" not in " ".join(response.invocation.argv)


def test_the_environment_reaches_the_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TECHTREE_HOME and provider authentication must survive the call."""
    monkeypatch.setenv("TECHTREE_HOME", str(tmp_path / "home"))
    _fake_cli_printing(
        tmp_path,
        monkeypatch,
        "print(json.dumps({'schema_version': 'techtree.cli.v1', 'command': 'doctor',"
        " 'ok': True, 'data': {'home': os.environ.get('TECHTREE_HOME')},"
        " 'error': None, 'messages': [], 'warnings': [], 'next_actions': []}))",
    )

    envelope = invoke_cli(["doctor"])

    assert envelope["data"]["home"] == str(tmp_path / "home")


# Release verification -------------------------------------------------------------


def test_a_matching_cli_release_verifies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    core = load_embedded_release_core()
    payload = {
        "release_id": core.release_id,
        "cli_version": core.cli_version,
        "package_version": "0.1.0",
        "protocol_version": core.protocol_version,
        "release_core_digest": release_core_digest(core),
        "engine_digest": core.engine_digest,
        "catalog_digest": core.catalog_digest,
        "intro_climb_reference": core.intro_climb_reference,
        "source_commit": "a" * 40,
    }
    cli = _fake_cli_printing(
        tmp_path, monkeypatch, print_envelope(command="release info", data=payload)
    )

    result = verify_cli_release(core)

    assert result["compatible"] is True
    assert result["mismatches"] == []
    assert cli.recorded_argv()[0][:2] == ["release", "info"]


def test_a_different_cli_release_is_reported_coordinate_by_coordinate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    core = load_embedded_release_core()
    payload = {
        "release_id": "0.9.9",
        "cli_version": "0.9.9",
        "package_version": "0.9.9",
        "protocol_version": core.protocol_version,
        "release_core_digest": "sha256:" + "c" * 64,
        "engine_digest": core.engine_digest,
        "catalog_digest": core.catalog_digest,
        "intro_climb_reference": core.intro_climb_reference,
        "source_commit": "b" * 40,
    }
    _fake_cli_printing(
        tmp_path, monkeypatch, print_envelope(command="release info", data=payload)
    )

    result = verify_cli_release(core)

    assert result["compatible"] is False
    assert set(result["mismatches"]) == {
        "release_core_digest",
        "release_id",
        "cli_version",
    }
