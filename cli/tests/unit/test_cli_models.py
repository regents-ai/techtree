"""The machine-readable CLI surface. Spec section 11.14.

These are the invariants a host agent depends on without reading any prose: a
successful response never carries an error, a failed one always does, and there
are never more than three next actions to choose between. The envelope enforces
them, so a command cannot emit an ambiguous response even by mistake.

``NextAction`` gets its own tests because an action nobody can carry out is
worse than no action at all — it looks like an offer and behaves like a dead
end.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError as PydanticValidationError

from techtree.constants import CLI_SCHEMA_VERSION
from techtree.models.cli import (
    MAX_NEXT_ACTIONS,
    CheckStatus,
    CliEnvelope,
    CliError,
    CliMessage,
    DoctorCheck,
    MessageLevel,
    NextAction,
)


def action(identifier: str = "install_engine") -> NextAction:
    """Build a runnable next action."""
    return NextAction(
        id=identifier,
        label="Install the evaluation engine",
        reason=None,
        cli=["techtree", "engine", "install"],
        hermes_tool=None,
        hermes_args=None,
        requires_user_confirmation=False,
    )


def envelope(**overrides: Any) -> CliEnvelope[CliError]:
    """Build a successful envelope, optionally overriding one part of it."""
    fields: dict[str, Any] = {
        "schema_version": CLI_SCHEMA_VERSION,
        "ok": True,
        "command": "climb list",
        "data": None,
        "messages": [],
        "warnings": [],
        "next_actions": [],
        "error": None,
    }
    fields.update(overrides)
    return CliEnvelope[CliError](**fields)


def error() -> CliError:
    """Build a machine-safe error payload."""
    return CliError(
        code="engine_error",
        message="The evaluation engine is not installed.",
        retryable=False,
        details={},
    )


def test_a_successful_envelope_carries_no_error() -> None:
    assert envelope().error is None


def test_success_with_an_error_is_rejected() -> None:
    with pytest.raises(PydanticValidationError, match="reports no error"):
        envelope(error=error())


def test_failure_without_an_error_is_rejected() -> None:
    with pytest.raises(PydanticValidationError, match="must say why it failed"):
        envelope(ok=False)


def test_a_failed_envelope_carries_an_error() -> None:
    assert envelope(ok=False, error=error()).error is not None


def test_three_next_actions_are_allowed() -> None:
    actions = [action(f"action_{index}") for index in range(MAX_NEXT_ACTIONS)]

    assert len(envelope(next_actions=actions).next_actions) == MAX_NEXT_ACTIONS


def test_a_fourth_next_action_is_rejected() -> None:
    actions = [action(f"action_{index}") for index in range(MAX_NEXT_ACTIONS + 1)]

    with pytest.raises(PydanticValidationError):
        envelope(next_actions=actions)


def test_repeated_next_action_identifiers_are_rejected() -> None:
    with pytest.raises(PydanticValidationError, match="distinct identifiers"):
        envelope(next_actions=[action(), action()])


def test_an_envelope_forbids_unknown_fields() -> None:
    with pytest.raises(PydanticValidationError, match="Extra inputs"):
        envelope(trace_url="https://example.invalid")


def test_a_next_action_must_be_runnable_by_something() -> None:
    with pytest.raises(PydanticValidationError, match="must offer"):
        NextAction(
            id="do_something",
            label="Do something",
            reason=None,
            cli=None,
            hermes_tool=None,
            hermes_args=None,
            requires_user_confirmation=False,
        )


def test_a_cli_next_action_needs_a_command_name() -> None:
    with pytest.raises(PydanticValidationError, match="at least the command name"):
        NextAction(
            id="do_something",
            label="Do something",
            reason=None,
            cli=[],
            hermes_tool=None,
            hermes_args=None,
            requires_user_confirmation=False,
        )


def test_host_agent_arguments_need_a_tool_to_call() -> None:
    with pytest.raises(PydanticValidationError, match="nothing to call"):
        NextAction(
            id="do_something",
            label="Do something",
            reason=None,
            cli=["techtree", "climb", "list"],
            hermes_tool=None,
            hermes_args={"slug": "hello-world-climb"},
            requires_user_confirmation=False,
        )


def test_an_action_can_require_confirmation_before_a_machine_runs_it() -> None:
    confirmed = NextAction(
        id="start_run",
        label="Start the run",
        reason="This consumes budget.",
        cli=["techtree", "climb", "start"],
        hermes_tool="techtree_climb_start",
        hermes_args={"draft_id": "draft_1"},
        requires_user_confirmation=True,
    )

    assert confirmed.requires_user_confirmation is True


def test_messages_carry_a_level_and_optional_code() -> None:
    message = CliMessage(level=MessageLevel.WARNING, code=None, text="Heads up.")

    assert message.level is MessageLevel.WARNING
    assert message.code is None


def test_a_passing_doctor_check_cannot_block() -> None:
    with pytest.raises(PydanticValidationError, match="cannot block"):
        DoctorCheck(
            id="python_version",
            label="Python version",
            status=CheckStatus.PASS,
            detail="Python 3.12 is available.",
            blocking=True,
            metadata={},
        )


def test_a_failing_doctor_check_may_block() -> None:
    check = DoctorCheck(
        id="engine_installed",
        label="Managed engine",
        status=CheckStatus.FAIL,
        detail="The evaluation engine is not installed.",
        blocking=True,
        metadata={"digest": None},
    )

    assert check.blocking is True
