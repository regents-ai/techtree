"""Typed errors, exit codes, and the CLI projection. Spec section 10.5.

The exit-code tests exist because a host agent branches on the number without
reading the output. Changing one silently would break automation that has no
way to notice.

Decision 0036: nothing here inspects an error for credential-shaped text. What
the projection still does to a message is flatten it onto one line and
normalise memory addresses, so the same failure reads the same way twice, and
those two behaviours are what the last section covers.
"""

from __future__ import annotations

import pytest

from techtree.canonical import sha256_digest_bytes
from techtree.errors import (
    EXIT_AUTHENTICATION,
    EXIT_CANCELLED,
    EXIT_CONFLICT,
    EXIT_ENGINE,
    EXIT_ERROR,
    EXIT_NOT_FOUND,
    EXIT_POLICY,
    EXIT_PREREQUISITE,
    EXIT_RUN,
    EXIT_USAGE,
    EXIT_VALIDATION,
    EXIT_VERIFICATION,
    AuthenticationError,
    CancellationError,
    ConflictError,
    EngineError,
    NotFoundError,
    PolicyError,
    PrerequisiteError,
    RunError,
    TechtreeError,
    UsageError,
    ValidationError,
    VerificationError,
    error_to_cli_error,
    exit_code_for,
    stable_exception_message,
)
from techtree.models.cli import CliEnvelope, CliError, NextAction

DIGEST = sha256_digest_bytes(b"object")


# ---------------------------------------------------------------------------
# The hierarchy and its exit codes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("error_type", "code", "exit_code"),
    [
        (TechtreeError, "techtree_error", EXIT_ERROR),
        (UsageError, "usage_error", EXIT_USAGE),
        (ValidationError, "validation_error", EXIT_VALIDATION),
        (PrerequisiteError, "prerequisite_error", EXIT_PREREQUISITE),
        (NotFoundError, "not_found", EXIT_NOT_FOUND),
        (ConflictError, "conflict", EXIT_CONFLICT),
        (AuthenticationError, "authentication_error", EXIT_AUTHENTICATION),
        (PolicyError, "policy_error", EXIT_POLICY),
        (EngineError, "engine_error", EXIT_ENGINE),
        (RunError, "run_error", EXIT_RUN),
        (VerificationError, "verification_error", EXIT_VERIFICATION),
        (CancellationError, "cancelled", EXIT_CANCELLED),
    ],
)
def test_each_error_fixes_its_code_and_exit_code(
    error_type: type[TechtreeError], code: str, exit_code: int
) -> None:
    error = error_type("something went wrong")

    assert error.code == code
    assert error.exit_code == exit_code
    assert exit_code_for(error) == exit_code
    assert isinstance(error, TechtreeError)


def test_exit_codes_are_distinct() -> None:
    codes = [
        EXIT_ERROR,
        EXIT_USAGE,
        EXIT_VALIDATION,
        EXIT_PREREQUISITE,
        EXIT_NOT_FOUND,
        EXIT_CONFLICT,
        EXIT_AUTHENTICATION,
        EXIT_POLICY,
        EXIT_ENGINE,
        EXIT_RUN,
        EXIT_VERIFICATION,
        EXIT_CANCELLED,
    ]

    assert len(set(codes)) == len(codes)


def test_an_untyped_exception_is_an_internal_defect() -> None:
    assert exit_code_for(RuntimeError("boom")) == EXIT_ERROR


def test_call_sites_may_override_the_defaults() -> None:
    error = ValidationError(
        "membership does not match",
        code="membership_mismatch",
        retryable=True,
        details={"expected": 20, "actual": 19},
    )

    assert error.code == "membership_mismatch"
    assert error.retryable is True
    assert error.details == {"expected": 20, "actual": 19}
    assert error.exit_code == EXIT_VALIDATION


def test_errors_are_not_retryable_by_default() -> None:
    assert TechtreeError("x").retryable is False


def test_an_error_carries_no_next_actions_by_default() -> None:
    assert TechtreeError("x").next_actions == []


def test_an_error_can_carry_the_next_actions_the_cli_should_offer() -> None:
    action = NextAction(
        id="install_engine",
        label="Install the evaluation engine",
        reason="The engine this Climb requires is not installed.",
        cli=["techtree", "engine", "install"],
        hermes_tool=None,
        hermes_args=None,
        requires_user_confirmation=False,
    )

    error = PrerequisiteError("the engine is not installed", next_actions=[action])

    assert [item.id for item in error.next_actions] == ["install_engine"]


def test_details_default_to_an_empty_mapping() -> None:
    assert TechtreeError("x").details == {}


# ---------------------------------------------------------------------------
# The CLI projection
# ---------------------------------------------------------------------------


def test_error_to_cli_error_keeps_the_machine_facing_fields() -> None:
    error = EngineError(
        "the engine could not be installed",
        retryable=True,
        details={"digest": DIGEST},
    )

    projected = error_to_cli_error(error)

    assert isinstance(projected, CliError)
    assert projected.code == "engine_error"
    assert projected.message == "the engine could not be installed"
    assert projected.retryable is True
    assert projected.details == {"digest": DIGEST}


def test_error_to_cli_error_repeats_the_message_word_for_word() -> None:
    """Decision 0036: a message says what the failing thing said."""
    error = AuthenticationError('rejected: {"api_key": "sk-live-abcdef123456"}')

    projected = error_to_cli_error(error)

    assert projected.message == 'rejected: {"api_key": "sk-live-abcdef123456"}'


def test_error_to_cli_error_carries_the_details_it_was_given() -> None:
    """Details are counts, identifiers and paths, and travel unchanged."""
    error = EngineError(
        "the engine could not be installed",
        details={
            "exit_code": 9,
            "timeout_seconds": 1.5,
            "retryable": True,
            "digest": DIGEST,
            "available": ["hello-world-climb@1"],
            "detail": "error: no index found at https://pypi.corp.example/simple",
            "cause": None,
        },
    )

    projected = error_to_cli_error(error)

    assert projected.details == {
        "exit_code": 9,
        "timeout_seconds": 1.5,
        "retryable": True,
        "digest": DIGEST,
        "available": ["hello-world-climb@1"],
        "detail": "error: no index found at https://pypi.corp.example/simple",
        "cause": None,
    }


def test_error_to_cli_error_does_not_carry_next_actions() -> None:
    """Next actions live on the envelope, not inside the error payload."""
    assert "next_actions" not in CliError.model_fields


def test_a_projected_error_fits_a_failure_envelope() -> None:
    envelope = CliEnvelope[CliError](
        schema_version="techtree.cli.v1",
        ok=False,
        command="engine install",
        data=None,
        messages=[],
        warnings=[],
        next_actions=[],
        error=error_to_cli_error(EngineError("the engine could not be installed")),
    )

    assert envelope.ok is False
    assert envelope.error is not None


# ---------------------------------------------------------------------------
# Message stability
# ---------------------------------------------------------------------------


def test_a_memory_address_is_stabilized() -> None:
    """A repr's address changes every process; the message must not."""
    message = stable_exception_message(
        RuntimeError("<object at 0x7f9c8b2a1d30> is not serializable")
    )

    assert "0x7f9c8b2a1d30" not in message
    assert "0x<address>" in message


def test_a_digest_is_not_mistaken_for_an_address() -> None:
    """Digests and task hashes are exactly what an operator needs to see."""
    message = stable_exception_message(RuntimeError(f"membership mismatch {DIGEST}"))

    assert DIGEST in message


def test_whitespace_is_collapsed() -> None:
    assert stable_exception_message(RuntimeError("one\n  two\t three")) == (
        "one two three"
    )


def test_an_empty_message_falls_back_to_the_exception_type() -> None:
    assert stable_exception_message(RuntimeError("")) == "RuntimeError"
