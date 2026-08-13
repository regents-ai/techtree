"""Typed errors, exit codes, and the secret scrubber. Spec section 10.5.

The exit-code tests exist because a host agent branches on the number without
reading the output. Changing one silently would break automation that has no
way to notice.

The scrubber tests carry two specific regressions found while verifying the
protocol core: an ``Authorization: Bearer <token>`` header redacted the wrong
half, and a quoted JSON key such as ``"api_key": "..."`` slipped through
because the closing quote broke the name match. Both are named tests here so a
future rewrite of those regular expressions cannot quietly reintroduce them.

The scrubber must also *not* redact the identifiers an operator needs — digests,
task hashes, and filesystem paths — so those are tested just as explicitly.
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
    REDACTED,
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
    sanitize_exception_message,
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


def test_error_to_cli_error_scrubs_the_message() -> None:
    error = AuthenticationError('rejected: {"api_key": "sk-live-abcdef123456"}')

    projected = error_to_cli_error(error)

    assert "sk-live-abcdef123456" not in projected.message
    assert REDACTED in projected.message


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
# The secret scrubber
# ---------------------------------------------------------------------------


def test_bearer_token_regression() -> None:
    """Regression: the scheme survives, the token does not."""
    message = sanitize_exception_message(
        RuntimeError("request failed: Authorization: Bearer sk-live-abcdef123456789")
    )

    assert "sk-live-abcdef123456789" not in message
    assert REDACTED in message


def test_quoted_json_key_regression() -> None:
    """Regression: a closing quote in the name must not break the match."""
    message = sanitize_exception_message(
        RuntimeError('config rejected: {"api_key": "abcdefghijklmnopqrstuvwxyz"}')
    )

    assert "abcdefghijklmnopqrstuvwxyz" not in message
    assert REDACTED in message


@pytest.mark.parametrize(
    "text",
    [
        "TECHTREE_API_KEY=sk-live-abcdef123456",
        "password: hunter2hunter2hunter2",
        "secret = 'abcdefghijklmnopqrst'",
        'authorization: "Basic dXNlcjpwYXNz"',
        "access_key=AKIAIOSFODNN7EXAMPLE",
        "my_service_token: ghp_abcdefghijklmnopqrstuvwxyz0123456789",
    ],
)
def test_secret_looking_assignments_are_redacted(text: str) -> None:
    message = sanitize_exception_message(RuntimeError(text))

    assert REDACTED in message


def test_a_prefixed_token_is_redacted_even_without_a_name() -> None:
    message = sanitize_exception_message(
        RuntimeError("upstream said ghp_abcdefghijklmnopqrstuvwxyz0123456789")
    )

    assert "ghp_abcdefghijklmnopqrstuvwxyz0123456789" not in message


def test_a_long_opaque_run_is_redacted() -> None:
    message = sanitize_exception_message(RuntimeError("value " + "Ab1_" * 15))

    assert REDACTED in message


def test_a_digest_survives_redaction() -> None:
    """Digests and task hashes are exactly what an operator needs to see."""
    message = sanitize_exception_message(RuntimeError(f"membership mismatch {DIGEST}"))

    assert DIGEST in message


def test_a_filesystem_path_survives_redaction() -> None:
    path = "/Users/example/Library/Application Support/techtree/runs/run_a"

    message = sanitize_exception_message(RuntimeError(f"missing {path}"))

    assert "/Users/example/Library/Application Support/techtree" in message


def test_a_credential_environment_variable_name_survives_redaction() -> None:
    """The name is configuration; hiding it would explain nothing to the user."""
    message = sanitize_exception_message(
        RuntimeError("credential_env=TECHTREE_MODEL_API_KEY is not set")
    )

    assert "TECHTREE_MODEL_API_KEY" in message
    assert REDACTED not in message


def test_a_token_budget_survives_redaction() -> None:
    message = sanitize_exception_message(RuntimeError("max_tokens=512 exceeded"))

    assert "max_tokens=512" in message


def test_a_memory_address_is_stabilized() -> None:
    message = sanitize_exception_message(
        RuntimeError("<object at 0x7f9c8b2a1d30> is not serializable")
    )

    assert "0x7f9c8b2a1d30" not in message
    assert "0x<address>" in message


def test_whitespace_is_collapsed() -> None:
    assert sanitize_exception_message(RuntimeError("one\n  two\t three")) == (
        "one two three"
    )


def test_an_empty_message_falls_back_to_the_exception_type() -> None:
    assert sanitize_exception_message(RuntimeError("")) == "RuntimeError"
