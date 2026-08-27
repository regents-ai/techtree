"""The CLI bridge. Specification sections 7.5 and 7.15, bridge tests.

These run a real executable named ``techtree`` on a temporary PATH rather than
patching ``subprocess``, because the claims being tested are about the process
the bridge actually starts: its argv, its flags, the absence of a shell, and
what it does with whatever comes back.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path

import pytest
from support import (
    FakeCli,
    install_fake_cli,
    platform_environment_names,
    print_envelope,
)
from techtree_hermes.bridge import (
    build_cli_argv,
    call_cli,
    cli_environment,
    invoke_cli,
    invoke_cli_human,
    resolve_techtree_binary,
    verify_cli_release,
)
from techtree_hermes.constants import CLI_ENVIRONMENT_ALLOWLIST, CLI_JSON_FLAGS
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


def test_stderr_is_repeated_word_for_word(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Decision 0036: what the CLI printed is what the diagnostic carries."""
    noisy = "warning: the index at https://pypi.internal/simple refused the request"
    _fake_cli_printing(
        tmp_path,
        monkeypatch,
        print_envelope() + f"\nsys.stderr.write({noisy!r})",
    )

    response = call_cli(["doctor"])

    assert response.stderr_excerpt == noisy


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
    """A credential is never read into an argument or a diagnostic.

    It does not reach the CLI's environment either — the next section holds
    that — but this is the older and narrower promise: whatever the bridge is
    given, it does not copy it into anything a caller or a model can read.
    """
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


# The environment a call is given ---------------------------------------------------
#
# The bridge builds it by name rather than handing over its own. A host agent's
# session is full of variables that belong to other software, and the CLI has
# no use for any of them; these check both halves of that — what must arrive,
# and what must not.


def _environment_reporting_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> FakeCli:
    """A CLI that answers with the environment it was actually given."""
    return _fake_cli_printing(
        tmp_path,
        monkeypatch,
        "print(json.dumps({'schema_version': 'techtree.cli.v1', 'command': 'doctor',"
        " 'ok': True, 'data': {'environment': dict(os.environ)},"
        " 'error': None, 'messages': [], 'warnings': [], 'next_actions': []}))",
    )


def test_the_environment_reaches_the_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TECHTREE_HOME must survive the call: it says which Techtree this is."""
    monkeypatch.setenv("TECHTREE_HOME", str(tmp_path / "home"))
    _environment_reporting_cli(tmp_path, monkeypatch)

    received = invoke_cli(["doctor"])["data"]["environment"]

    assert received["TECHTREE_HOME"] == str(tmp_path / "home")


def _unexplained_names(received: Mapping[str, str]) -> set[str]:
    """Names in a child's environment that this session cannot account for.

    A name is accounted for when it is on the allowlist — the bridge put it
    there — or when the platform puts it into every child it starts. Anything
    else present in both this session and the child came across when it should
    not have.
    """
    return (
        {name for name in received if name in os.environ}
        - set(CLI_ENVIRONMENT_ALLOWLIST)
        - platform_environment_names()
    )


def test_the_call_is_given_the_allowlist_and_nothing_else(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every allowlisted value arrives, and no other variable of this session does."""
    monkeypatch.setenv("TECHTREE_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("TECHTREE_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "aws-secret-must-never-appear")
    _environment_reporting_cli(tmp_path, monkeypatch)

    received = invoke_cli(["doctor"])["data"]["environment"]

    assert cli_environment().items() <= received.items()
    assert _unexplained_names(received) == set()
    assert "AWS_SECRET_ACCESS_KEY" not in received


def test_a_secret_the_cli_has_no_business_seeing_never_arrives(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The canary: a wallet key in the host session, and a call that runs anyway."""
    monkeypatch.setenv("FAKE_WALLET_KEY", "wallet-secret-must-never-appear")
    _environment_reporting_cli(tmp_path, monkeypatch)

    envelope = invoke_cli(["doctor"])

    assert "FAKE_WALLET_KEY" not in envelope["data"]["environment"]
    assert "wallet-secret-must-never-appear" not in json.dumps(envelope)


def test_the_terminal_path_is_given_the_same_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The streams are the caller's; the environment is still the allowlist."""
    report = tmp_path / "environment.json"
    monkeypatch.setenv("FAKE_WALLET_KEY", "wallet-secret-must-never-appear")
    _fake_cli_printing(
        tmp_path,
        monkeypatch,
        f"open({str(report)!r}, 'w', encoding='utf-8')"
        ".write(json.dumps(dict(os.environ)))",
    )

    assert invoke_cli_human(["watch", "run_" + "0" * 32]) == 0

    received = json.loads(report.read_text(encoding="utf-8"))
    assert cli_environment().items() <= received.items()
    assert _unexplained_names(received) == set()
    assert "FAKE_WALLET_KEY" not in received


def test_the_environment_is_built_by_name_from_the_fixed_list() -> None:
    """Nothing is matched by prefix or pattern: a name is on the list or it is not."""
    built = cli_environment(
        {
            "PATH": "/usr/bin",
            "TERM": "xterm-256color",
            "TECHTREE_ACCESS_TOKEN": "not-on-the-list",
            "AWS_SECRET_ACCESS_KEY": "not-on-the-list",
        }
    )

    assert built == {"PATH": "/usr/bin", "TERM": "xterm-256color"}


def test_a_name_that_is_not_set_is_not_invented() -> None:
    """An absent variable stays absent; the bridge passes values, it makes none."""
    built = cli_environment({"PATH": "/usr/bin"})

    assert built == {"PATH": "/usr/bin"}


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
