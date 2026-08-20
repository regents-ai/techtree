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
    sanitize_text,
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


#: A private package index, spelled the way uv reports one back. The
#: credential sits in the URL's userinfo, where no assignment rule and no
#: token-prefix rule would find it, which is what made this the vector worth
#: naming: WP11g S1.
INDEX_URL_WITH_TOKEN = "https://deploy:s3cr3t-p4ss@pypi.corp.example/simple"


def test_error_to_cli_error_scrubs_the_details_too() -> None:
    """WP11g S1: the message was scrubbed and the details rode out beside it."""
    error = EngineError(
        "building the engine environment failed",
        details={"detail": f"error: no index found at {INDEX_URL_WITH_TOKEN}"},
    )

    projected = error_to_cli_error(error)

    assert "s3cr3t-p4ss" not in str(projected.details)
    assert REDACTED in str(projected.details)


def test_the_details_walk_reaches_nested_strings() -> None:
    """A leak one level down is still a leak."""
    error = EngineError(
        "the engine could not be installed",
        details={
            "attempts": [
                {"index": INDEX_URL_WITH_TOKEN, "exit_code": 1},
                {"index": "https://pypi.org/simple", "exit_code": 2},
            ],
            "environment": {"UV_INDEX_URL": INDEX_URL_WITH_TOKEN},
        },
    )

    projected = error_to_cli_error(error)

    assert "s3cr3t-p4ss" not in str(projected.details)


def test_the_details_walk_leaves_everything_that_is_not_a_string_alone() -> None:
    """Details are counts and identifiers; scrubbing must not retype them."""
    error = EngineError(
        "the engine could not be installed",
        details={
            "exit_code": 9,
            "timeout_seconds": 1.5,
            "retryable": True,
            "digest": DIGEST,
            "available": ["hello-world-climb@1"],
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
        "cause": None,
    }


def test_a_url_credential_is_redacted_and_the_host_survives() -> None:
    """The operator still needs to know which index refused them."""
    scrubbed = sanitize_text(f"could not reach {INDEX_URL_WITH_TOKEN}")

    assert "deploy" not in scrubbed
    assert "s3cr3t-p4ss" not in scrubbed
    assert "pypi.corp.example/simple" in scrubbed
    assert f"https://{REDACTED}@pypi.corp.example/simple" in scrubbed


@pytest.mark.parametrize(
    "url",
    [
        "https://__token__:AbCdEf1234567890@pypi.corp.example/simple",
        "https://ghp_abcdefghijklmnopqrst@pypi.corp.example/simple",
        "http://user:pw@localhost:8080/simple",
        "git+ssh://git:key123@github.com/org/repo.git",
    ],
)
def test_every_shape_of_url_credential_is_redacted(url: str) -> None:
    scrubbed = sanitize_text(f"uv sync failed: --index-url {url}")

    assert REDACTED in scrubbed
    for secret in ("AbCdEf1234567890", "ghp_abcdefghijklmnopqrst", "pw", "key123"):
        if secret in url:
            assert secret not in scrubbed


def test_an_ordinary_url_is_left_alone() -> None:
    """No userinfo, nothing to redact. The coordinate must survive verbatim."""
    published = "https://techtree.sh/objects/hello-world-starter-v1/SKILL.md"

    assert sanitize_text(published) == published


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


@pytest.mark.parametrize(
    "text",
    [
        # The sentence a signed-out person reads on their first run. The word
        # after the colon is "the", and redacting it broke the sentence.
        "the evaluation model endpoint has no credential: the Prime CLI "
        "configuration on this machine holds no key",
        "no credential: this machine is signed out",
        "the token: no reasoning is included in the final answer",
        "password: your provider sets this in its own console",
    ],
)
def test_ordinary_prose_after_a_secret_looking_word_survives(text: str) -> None:
    """A word in a sentence is not a credential, and hiding it explains nothing."""
    assert sanitize_text(text) == text


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


def test_a_techtree_identifier_survives_redaction() -> None:
    """An error that names which campaign failed must keep naming it."""
    for prefix in ("campaign", "draft", "run", "receipt", "uplift", "policy"):
        identifier = f"{prefix}_93d932bd41a2aef87bd6ee2040f7e62a"
        message = sanitize_exception_message(RuntimeError(f"{identifier} failed"))

        assert identifier in message


def test_a_usage_record_survives_redaction() -> None:
    """NormalizedUsage's counts are what an operator needs on a spend question."""
    usage = (
        '{"input_tokens": 120, "output_tokens": 46, '
        '"total_tokens": 166, "cached_input_tokens": 0}'
    )
    message = sanitize_exception_message(RuntimeError(usage))

    assert '"input_tokens": 120' in message
    assert '"output_tokens": 46' in message
    assert '"cached_input_tokens": 0' in message


def test_a_prefixed_identifier_shaped_credential_is_still_redacted() -> None:
    """The exemption is exactly the Techtree ID shape, nothing wider."""
    not_ids = (
        # Right length, wrong prefix style for Techtree.
        "secret_fixture_0123456789abcdef01234567",
        # A Techtree prefix but a value that is not 32 lowercase hex.
        "campaign_93D932BD41A2AEF87BD6EE2040F7E62A",
        "campaign_notahexvalueatallnotahexvalueatall",
    )
    for value in not_ids:
        message = sanitize_exception_message(RuntimeError(f"leaked {value}"))

        assert value not in message


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
