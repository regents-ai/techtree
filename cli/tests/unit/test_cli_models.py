"""The machine-readable CLI surface. ``docs/v0.2/MACHINE_CONTRACT.md``.

These are the invariants a host agent depends on without reading any prose: a
successful response never carries an error, a failed one always does, and there
are never more than three next actions to choose between. The envelope enforces
them, so a command cannot emit an ambiguous response even by mistake.

``NextAction`` gets its own tests because an action nobody can carry out is
worse than no action at all — it looks like an offer and behaves like a dead
end, and in ``techtree.cli.v2`` "carry out" means building one invocation out
of the named arguments without parsing anything.

``CliBlocker`` and ``ContentRef`` get theirs for the same reason: a blocker
that forbids nothing is a warning under the wrong name, and a reference nothing
can be fetched by is not a reference.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError as PydanticValidationError

from techtree.constants import CLI_SCHEMA_VERSION
from techtree.models.cli import (
    MAX_NEXT_ACTIONS,
    CheckStatus,
    CliBlocker,
    CliEnvelope,
    CliError,
    CliUnknown,
    CliWarning,
    ContentRef,
    DataEgress,
    DoctorCheck,
    NextAction,
    Operation,
    RetryClass,
    SideEffect,
    command_line,
    invocation,
)


def action(*command: str, **overrides: Any) -> NextAction:
    """Build a runnable next action."""
    fields: dict[str, Any] = {
        "operation": Operation.ACTION_EXECUTE,
        "prepared_arguments": invocation(*(command or ("engine", "install"))),
        "expected_state_digest": None,
        "side_effect": SideEffect.LOCAL_STATE,
        "approval_required": False,
        "retry_class": RetryClass.SAFE,
        "estimated_cost": None,
        "data_egress": DataEgress.PACKAGE_INDEX,
        "reason": "The engine this Climb requires is not installed.",
    }
    fields.update(overrides)
    return NextAction(**fields)


def envelope(**overrides: Any) -> CliEnvelope[dict[str, str]]:
    """Build a successful envelope, optionally overriding one part of it."""
    fields: dict[str, Any] = {
        "schema_version": CLI_SCHEMA_VERSION,
        "operation": Operation.PLAN_INSPECT,
        "ok": True,
        "state_digest": None,
        "facts": {},
        "unknowns": [],
        "blockers": [],
        "warnings": [],
        "content_refs": [],
        "next_actions": [],
        "error": None,
    }
    fields.update(overrides)
    return CliEnvelope[dict[str, str]](**fields)


def error() -> CliError:
    """Build a machine-safe error payload."""
    return CliError(
        code="engine_error",
        message="The evaluation engine is not installed.",
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
    actions = [action("engine", "install"), action("doctor"), action("climb", "list")]

    assert len(envelope(next_actions=actions).next_actions) == MAX_NEXT_ACTIONS


def test_a_fourth_next_action_is_rejected() -> None:
    actions = [
        action("engine", "install"),
        action("doctor"),
        action("climb", "list"),
        action("setup"),
    ]

    with pytest.raises(PydanticValidationError):
        envelope(next_actions=actions)


def test_the_same_step_offered_twice_is_rejected() -> None:
    """One operation with one set of arguments is one step, offered once."""
    with pytest.raises(PydanticValidationError, match="must be distinct"):
        envelope(next_actions=[action(), action()])


def test_one_operation_may_be_offered_with_different_arguments() -> None:
    """Two readings of two different runs are two steps, not a repeat."""
    offered = envelope(
        next_actions=[
            action("run", "status", operation=Operation.RUN_STATUS),
            action(
                "run",
                "status",
                operation=Operation.RUN_STATUS,
                prepared_arguments=invocation(
                    "run", "status", arguments=["run_" + "0" * 32]
                ),
            ),
        ]
    )

    assert len(offered.next_actions) == 2


def test_an_envelope_forbids_unknown_fields() -> None:
    with pytest.raises(PydanticValidationError, match="Extra inputs"):
        envelope(trace_url="https://example.invalid")


def test_an_action_names_one_invocation_and_nothing_else() -> None:
    for prepared in (
        {},
        {"command": ["engine", "install"]},
        {"command": ["engine", "install"], "arguments": [], "options": {}, "cli": []},
    ):
        with pytest.raises(PydanticValidationError, match="exactly"):
            action(prepared_arguments=prepared)


def test_an_action_needs_a_command_path() -> None:
    with pytest.raises(PydanticValidationError, match="at least one segment"):
        action(prepared_arguments=invocation())


def test_an_action_holds_only_literals() -> None:
    with pytest.raises(PydanticValidationError, match="literal string"):
        action(prepared_arguments=invocation("engine", "install", arguments=[" "]))


def test_an_option_is_named_as_it_is_spelled() -> None:
    with pytest.raises(PydanticValidationError, match="as it is spelled"):
        action(
            prepared_arguments=invocation("doctor", options={"for-evaluation": True})
        )


def test_an_option_carries_its_value_or_says_it_takes_none() -> None:
    with pytest.raises(PydanticValidationError, match="carries its value"):
        action(prepared_arguments=invocation("doctor", options={"--climb": ""}))


def test_a_flag_that_says_no_is_refused_rather_than_rendered_as_yes() -> None:
    """``false`` is not "leave it out": the line would carry the flag anyway.

    An absent flag is not named. A ``--yes`` valued ``false`` that reached
    ``command_line`` would render as ``--yes``, which is the one mistake the
    approval flag exists to make impossible.
    """
    prepared = {
        "command": ["climb", "start"],
        "arguments": ["draft_" + "0" * 32],
        "options": {"--yes": False},
    }

    with pytest.raises(PydanticValidationError, match="carries its value"):
        action("climb", "start", prepared_arguments=prepared)


def test_an_action_renders_as_the_line_it_would_run() -> None:
    """Display and invocation are one list, so neither can drift."""
    offered = action(
        "climb",
        "prepare",
        prepared_arguments=invocation(
            "climb",
            "prepare",
            arguments=["hello-world-climb@1"],
            options={"--skill": "/tmp/SKILL.md", "--yes": True},
        ),
    )

    assert command_line(offered) == [
        "techtree",
        "climb",
        "prepare",
        "hello-world-climb@1",
        "--skill",
        "/tmp/SKILL.md",
        "--yes",
    ]


def test_an_action_can_require_a_person_before_a_machine_runs_it() -> None:
    confirmed = action(
        "climb",
        "start",
        approval_required=True,
        retry_class=RetryClass.HUMAN_DECISION_REQUIRED,
        side_effect=SideEffect.LOCAL_EXECUTION,
        data_egress=DataEgress.MODEL_PROVIDER,
        reason="This spends model tokens on inference.",
    )

    assert confirmed.approval_required is True


def test_a_blocker_names_what_it_forbids() -> None:
    with pytest.raises(PydanticValidationError, match="names the operations"):
        CliBlocker(id="x", text="Something is wrong.", blocks=[], resolvable_by=None)


def test_a_blocker_names_each_operation_once() -> None:
    with pytest.raises(PydanticValidationError, match="once"):
        CliBlocker(
            id="x",
            text="Something is wrong.",
            blocks=[Operation.PLAN_PREPARE, Operation.PLAN_PREPARE],
            resolvable_by=None,
        )


def test_a_content_reference_can_be_reached() -> None:
    with pytest.raises(PydanticValidationError, match="a path, a URL, or both"):
        ContentRef(
            id="proof",
            kind="proof_bundle",
            digest=None,
            path=None,
            url=None,
            media_type="application/json",
            byte_count=None,
        )


def test_an_unknown_is_not_a_warning() -> None:
    """They are different answers, and each has its own place to be said."""
    unknown = CliUnknown(
        id="result_cost",
        subject="/presentation/cost_usd",
        reason="This run recorded no operational evidence to cost it from.",
        resolvable_by=None,
    )
    warning = CliWarning(
        id="development_climb", text="Its results prove nothing.", resolvable_by=None
    )

    assert envelope(unknowns=[unknown], warnings=[warning]).unknowns[0].id == (
        "result_cost"
    )
    assert warning.resolvable_by is None


def test_an_unknowns_subject_is_a_json_pointer_or_nothing() -> None:
    """A caller resolves it against ``facts``, so it has to be resolvable.

    A field name on its own is the shape somebody reaches for first and no
    resolver accepts, which is why it is refused here rather than at whatever
    reads it.
    """
    for pointer in ("", "/presentation/cost_usd", "/a~0b", "/a~1b"):
        assert (
            CliUnknown(id="x", subject=pointer, reason="r", resolvable_by=None).subject
            == pointer
        )

    for not_a_pointer in ("cost_usd", "presentation/cost_usd", "/a~2b"):
        with pytest.raises(PydanticValidationError):
            CliUnknown(id="x", subject=not_a_pointer, reason="r", resolvable_by=None)


def test_facts_is_an_object_in_every_envelope() -> None:
    """One shape whatever a caller asked, so one reader handles every answer.

    Built the way the CLI builds one, with the payload type left open: that is
    the construction where a list would otherwise pass, and where ``climb
    list`` used to answer with a bare array.
    """
    fields: dict[str, Any] = {
        "schema_version": CLI_SCHEMA_VERSION,
        "operation": Operation.PLAN_INSPECT,
        "ok": True,
        "state_digest": None,
        "facts": {},
        "unknowns": [],
        "blockers": [],
        "warnings": [],
        "content_refs": [],
        "next_actions": [],
        "error": None,
    }

    assert CliEnvelope[Any](**fields).facts == {}
    refused: list[Any] = [[], "ready", 7]
    for not_an_object in refused:
        with pytest.raises(PydanticValidationError, match="facts is an object"):
            CliEnvelope[Any](**{**fields, "facts": not_an_object})


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
