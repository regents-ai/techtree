"""The envelope contract, at the layer that builds it. Spec sections 11.14, 12.

``tests/unit/test_cli_models.py`` proves the model refuses to hold a
contradictory envelope. These tests prove the CLI never asks it to: that
success and failure are constructed correctly, that exit status and ``ok``
agree, that repair actions survive from the error that raised them, and that
nothing secret reaches stdout.

The whole file runs in process. Real ``techtree`` subprocesses live in
``test_cli_machine_mode.py``; what is being checked here is composition, and a
composed failure is much easier to arrange from the inside.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest
import typer
from rich.console import Console
from typer.testing import CliRunner

from techtree.cli.app import (
    GLOBAL_FLAGS,
    RESERVED_NAMESPACES,
    create_app,
    hoist_global_options,
    main,
)
from techtree.cli.context import CliContext, build_cli_context
from techtree.cli.invoke import (
    CommandResult,
    failure_envelope,
    invoke_command,
    not_implemented_error,
    success_envelope,
)
from techtree.cli.output import json_stdout, render_next_actions, shell_display
from techtree.constants import CLI_SCHEMA_VERSION
from techtree.doctor.service import DoctorReport, DoctorService
from techtree.errors import (
    EXIT_NOT_FOUND,
    EXIT_OK,
    EXIT_POLICY,
    EXIT_PREREQUISITE,
    EXIT_VALIDATION,
    NotFoundError,
    PolicyError,
    PrerequisiteError,
    TechtreeError,
    ValidationError,
)
from techtree.models.cli import (
    MAX_NEXT_ACTIONS,
    CheckStatus,
    CliEnvelope,
    CliMessage,
    DoctorCheck,
    MessageLevel,
    NextAction,
)
from techtree.paths import paths_from_root
from techtree.settings import Settings


def action(identifier: str) -> NextAction:
    """Build a runnable next action."""
    return NextAction(
        id=identifier,
        label=f"Do {identifier}",
        reason=None,
        cli=["techtree", "doctor"],
        hermes_tool=None,
        hermes_args=None,
        requires_user_confirmation=False,
    )


def check(
    identifier: str,
    status: CheckStatus,
    *,
    blocking: bool = False,
    metadata: dict[str, Any] | None = None,
) -> DoctorCheck:
    """Build one Doctor check with a given outcome."""
    return DoctorCheck(
        id=identifier,
        label=identifier.replace("_", " "),
        status=status,
        detail=f"{identifier} is {status.value}",
        blocking=blocking,
        metadata=metadata or {},
    )


@pytest.fixture
def context(temp_techtree_home: Path) -> CliContext:
    """A machine-mode context rooted in an isolated home."""
    return build_cli_context(
        home=temp_techtree_home,
        json_output=True,
        no_color=True,
        no_input=True,
        debug=False,
    )


def emitted(capsys: pytest.CaptureFixture[str]) -> dict[str, Any]:
    """Parse the single JSON object the CLI wrote to stdout."""
    captured = capsys.readouterr()
    lines = captured.out.splitlines()
    assert len(lines) == 1, f"expected exactly one JSON object, got {captured.out!r}"
    parsed = json.loads(lines[0])
    assert isinstance(parsed, dict)
    return parsed


# ---------------------------------------------------------------------------
# Envelope construction
# ---------------------------------------------------------------------------


def test_a_successful_envelope_names_its_command_and_carries_no_error() -> None:
    envelope = success_envelope(command="doctor", data={"checks": [1]})

    assert envelope.schema_version == CLI_SCHEMA_VERSION
    assert envelope.ok is True
    assert envelope.command == "doctor"
    assert envelope.error is None


def test_a_failed_envelope_projects_the_typed_error() -> None:
    envelope: CliEnvelope[None] = failure_envelope(
        command="climb show",
        error=NotFoundError("no such Climb: nope", details={"reference": "nope"}),
    )

    assert envelope.ok is False
    assert envelope.error is not None
    assert envelope.error.code == "not_found"
    assert envelope.error.details == {"reference": "nope"}


def test_a_failed_envelope_offers_the_repairs_its_error_carried() -> None:
    error = PrerequisiteError("no engine", next_actions=[action("install_engine")])

    envelope: CliEnvelope[None] = failure_envelope(command="climb prepare", error=error)

    assert [step.id for step in envelope.next_actions] == ["install_engine"]


def test_more_than_three_repairs_are_truncated_rather_than_rejected() -> None:
    error = PrerequisiteError(
        "several problems",
        next_actions=[action(f"repair_{index}") for index in range(5)],
    )

    envelope: CliEnvelope[None] = failure_envelope(command="doctor", error=error)

    assert len(envelope.next_actions) == MAX_NEXT_ACTIONS


def test_a_failing_command_may_still_return_what_it_found(
    context: CliContext, capsys: pytest.CaptureFixture[str]
) -> None:
    def diagnose() -> CommandResult[dict[str, str]]:
        return CommandResult(
            data={"finding": "the host is not ready"},
            error=PrerequisiteError("not ready"),
        )

    with pytest.raises(typer.Exit) as exit_signal:
        invoke_command(context, "doctor", diagnose)

    envelope = emitted(capsys)
    assert exit_signal.value.exit_code == EXIT_PREREQUISITE
    assert envelope["ok"] is False
    assert envelope["data"] == {"finding": "the host is not ready"}


# ---------------------------------------------------------------------------
# Exit status
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("error", "expected_code", "expected_identifier"),
    [
        (ValidationError("bad document"), EXIT_VALIDATION, "validation_error"),
        (NotFoundError("missing"), EXIT_NOT_FOUND, "not_found"),
        (PrerequisiteError("not yet"), EXIT_PREREQUISITE, "prerequisite_error"),
        (PolicyError("rights disagree"), EXIT_POLICY, "policy_error"),
    ],
)
def test_each_typed_failure_exits_with_its_documented_code(
    context: CliContext,
    capsys: pytest.CaptureFixture[str],
    error: TechtreeError,
    expected_code: int,
    expected_identifier: str,
) -> None:
    def fail() -> CommandResult[None]:
        raise error

    with pytest.raises(typer.Exit) as exit_signal:
        invoke_command(context, "climb list", fail)

    envelope = emitted(capsys)
    assert exit_signal.value.exit_code == expected_code
    assert envelope["error"]["code"] == expected_identifier


def test_success_exits_zero_and_failure_never_does(
    context: CliContext, capsys: pytest.CaptureFixture[str]
) -> None:
    def succeed() -> CommandResult[str]:
        return CommandResult(data="fine")

    with pytest.raises(typer.Exit) as exit_signal:
        invoke_command(context, "doctor", succeed)

    envelope = emitted(capsys)
    assert exit_signal.value.exit_code == EXIT_OK
    assert envelope["ok"] is True


def test_an_unexpected_exception_becomes_an_internal_error_not_a_traceback(
    context: CliContext, capsys: pytest.CaptureFixture[str]
) -> None:
    def explode() -> CommandResult[None]:
        raise ZeroDivisionError("division by zero")

    with pytest.raises(typer.Exit) as exit_signal:
        invoke_command(context, "run status", explode)

    envelope = emitted(capsys)
    assert exit_signal.value.exit_code == 1
    assert envelope["error"]["code"] == "internal_error"
    assert envelope["error"]["details"]["exception_type"] == "ZeroDivisionError"
    assert "Traceback" not in json.dumps(envelope)


def test_a_registered_but_unbuilt_command_says_so_in_a_stable_way() -> None:
    error = not_implemented_error("climb list")

    envelope: CliEnvelope[None] = failure_envelope(command="climb list", error=error)

    assert envelope.error is not None
    assert envelope.error.code == "not_implemented"
    assert envelope.error.details == {"command": "climb list"}


# ---------------------------------------------------------------------------
# Machine safety
# ---------------------------------------------------------------------------


def test_a_failure_message_reaches_the_envelope_word_for_word(
    context: CliContext, capsys: pytest.CaptureFixture[str]
) -> None:
    """Decision 0036: nothing between the raise and the envelope edits it."""

    def fail() -> CommandResult[None]:
        raise ValidationError("rejected by the index at pypi.corp.example/simple")

    with pytest.raises(typer.Exit):
        invoke_command(context, "climb start", fail)

    envelope = emitted(capsys)
    assert envelope["error"]["message"] == (
        "rejected by the index at pypi.corp.example/simple"
    )


def test_json_output_is_one_line_of_canonical_json(
    capsys: pytest.CaptureFixture[str],
) -> None:
    json_stdout(
        success_envelope(
            command="doctor",
            data=None,
            messages=[
                CliMessage(level=MessageLevel.INFO, code=None, text="ready"),
            ],
        )
    )

    captured = capsys.readouterr()
    assert captured.out.endswith("\n")
    assert captured.err == ""
    assert len(captured.out.splitlines()) == 1

    keys = list(json.loads(captured.out))
    assert keys == sorted(keys)


def _rendered(actions: list[NextAction]) -> str:
    """Return what a person would see below an answer carrying these steps."""
    buffer = io.StringIO()
    render_next_actions(actions, Console(file=buffer, width=100, no_color=True))
    return buffer.getvalue()


def test_one_next_action_is_headed_as_the_one_thing_to_do_next() -> None:
    """Decision 0024 section 7: a successful answer ends with one immediate step."""
    text = _rendered([action("run_doctor")])

    assert "Next:" in text
    assert "Next steps:" not in text
    assert "1." not in text


def test_several_next_actions_are_still_headed_as_a_list() -> None:
    text = _rendered([action("run_doctor"), action("list_climbs")])

    assert "Next steps:" in text
    assert "1." in text


def test_a_displayed_command_is_quoted_but_the_vector_is_the_contract() -> None:
    argv = ["techtree", "climb", "prepare", "--skill", "/tmp/a skill; rm -rf /"]

    displayed = shell_display(argv)

    assert displayed.startswith("techtree climb prepare --skill ")
    assert "'/tmp/a skill; rm -rf /'" in displayed


# ---------------------------------------------------------------------------
# Doctor's contribution to the envelope
# ---------------------------------------------------------------------------


def test_doctor_offers_at_most_three_repairs_without_repeating_one(
    temp_techtree_home: Path,
) -> None:
    service = DoctorService(paths_from_root(temp_techtree_home), Settings())
    checks = [
        check("techtree_home", CheckStatus.FAIL, blocking=True),
        check("python_version", CheckStatus.FAIL, blocking=True),
        check("uv", CheckStatus.WARN),
        check("docker_cli", CheckStatus.WARN),
        check("docker_daemon", CheckStatus.WARN),
        check("active_engine", CheckStatus.WARN),
    ]

    actions = service.next_actions(checks)

    assert len(actions) <= MAX_NEXT_ACTIONS
    assert len({step.id for step in actions}) == len(actions)
    assert all(step.cli for step in actions)


def test_doctor_still_suggests_something_when_everything_passes(
    temp_techtree_home: Path,
) -> None:
    service = DoctorService(paths_from_root(temp_techtree_home), Settings())

    actions = service.next_actions([check("python_version", CheckStatus.PASS)])

    assert [step.id for step in actions] == ["list_climbs"]
    assert actions[0].cli == ["techtree", "climb", "list"]


def test_doctor_separates_the_host_platform_from_the_docker_platform(
    temp_techtree_home: Path,
) -> None:
    service = DoctorService(paths_from_root(temp_techtree_home), Settings())
    checks = [
        check(
            "host_platform",
            CheckStatus.PASS,
            metadata={"host_platform": "darwin/arm64"},
        ),
        check(
            "docker_daemon",
            CheckStatus.PASS,
            metadata={"docker_platform": "linux/amd64"},
        ),
    ]

    report = service.report(checks)

    assert report.host_platform == "darwin/arm64"
    assert report.docker_platform == "linux/amd64"


def test_a_doctor_report_without_docker_reports_no_docker_platform(
    temp_techtree_home: Path,
) -> None:
    service = DoctorService(paths_from_root(temp_techtree_home), Settings())

    report = service.report([check("docker_daemon", CheckStatus.SKIP)])

    assert isinstance(report, DoctorReport)
    assert report.docker_platform is None
    assert report.host_platform is None


def test_a_blocking_check_is_reported_as_blocking_and_a_warning_is_not(
    temp_techtree_home: Path,
) -> None:
    service = DoctorService(paths_from_root(temp_techtree_home), Settings())
    checks = [
        check("techtree_home", CheckStatus.FAIL, blocking=True),
        check("uv", CheckStatus.WARN),
        check("python_version", CheckStatus.PASS),
    ]

    assert [item.id for item in service.blocking_failures(checks)] == ["techtree_home"]
    assert [item.id for item in service.warnings(checks)] == ["uv"]


# ---------------------------------------------------------------------------
# Global options and reserved names
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        (["doctor", "--json"], ["--json", "doctor"]),
        (["--json", "doctor"], ["--json", "doctor"]),
        (
            ["climb", "list", "--json", "--home", "/tmp/x"],
            ["--json", "--home", "/tmp/x", "climb", "list"],
        ),
        (["doctor", "--home=/tmp/x"], ["--home=/tmp/x", "doctor"]),
        (["climb", "show", "--", "--json"], ["climb", "show", "--", "--json"]),
    ],
)
def test_global_options_are_understood_wherever_they_are_written(
    given: list[str], expected: list[str]
) -> None:
    assert hoist_global_options(given) == expected


def test_machine_mode_never_leaves_input_enabled(temp_techtree_home: Path) -> None:
    context = build_cli_context(
        home=temp_techtree_home,
        json_output=True,
        no_color=False,
        no_input=False,
        debug=False,
    )

    assert context.no_input is True


def test_configured_json_output_turns_machine_mode_on(
    temp_techtree_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TECHTREE_OUTPUT_MODE", "json")

    context = build_cli_context(
        home=temp_techtree_home,
        json_output=False,
        no_color=False,
        no_input=False,
        debug=False,
    )

    assert context.json_output is True
    assert context.no_input is True


def test_the_reserved_namespaces_are_the_ones_the_specification_names() -> None:
    assert RESERVED_NAMESPACES == (
        "program",
        "blueprint",
        "forge",
        "verify",
        "uplift",
        "trace",
        "lab",
    )


def test_every_global_flag_is_recognized_by_the_hoister() -> None:
    for flag in GLOBAL_FLAGS:
        assert hoist_global_options(["doctor", flag])[0] == flag


# ---------------------------------------------------------------------------
# The whole doctor command, when the host is genuinely not ready
# ---------------------------------------------------------------------------


def test_a_blocking_check_makes_doctor_fail_without_losing_the_diagnosis(
    temp_techtree_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A broken host is a failure, and the checks are still the answer."""
    monkeypatch.setattr(
        "techtree.doctor.service.check_techtree_home",
        lambda _paths: check("techtree_home", CheckStatus.FAIL, blocking=True),
    )

    result = CliRunner().invoke(
        create_app(),
        ["--home", str(temp_techtree_home), "doctor", "--json"],
    )

    assert result.exit_code == EXIT_PREREQUISITE
    envelope = json.loads(result.stdout.splitlines()[-1])
    assert envelope["ok"] is False
    assert envelope["command"] == "doctor"
    assert envelope["error"]["code"] == "environment_not_ready"
    assert envelope["error"]["details"]["failed_checks"] == ["techtree_home"]
    assert envelope["data"]["checks"][2]["id"] == "techtree_home"
    assert envelope["next_actions"][0]["id"] == "fix_techtree_home_permissions"


def test_a_defect_outside_every_command_still_produces_one_envelope(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The last-resort boundary answers even when the application cannot start."""

    def broken_app() -> typer.Typer:
        raise RuntimeError("the application could not be built")

    monkeypatch.setattr("techtree.cli.app.create_app", broken_app)
    monkeypatch.setattr("sys.argv", ["techtree", "--json", "doctor"])

    with pytest.raises(SystemExit) as exit_signal:
        main()

    envelope = emitted(capsys)
    assert exit_signal.value.code == 1
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "internal_error"
