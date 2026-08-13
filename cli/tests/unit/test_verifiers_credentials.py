"""Diagnosing evaluation auth without ever handling a secret. Spec section 6.9.

The interesting property of this module is negative, so most of these tests are
searches: build the object, then look for the credential's value anywhere in
what came back. A test that only asserted "available is True" would pass
happily against an implementation that returned the key alongside it.

Every test sets its own environment through ``monkeypatch``, and none of them
reads a real credential.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from techtree.errors import AuthenticationError
from techtree.models.campaign import ModelSpec
from techtree.models.engine import EngineInstallation
from techtree.verifiers.credentials import (
    PRIME_CREDENTIAL_ENV,
    credential_status,
    redacted_environment,
    require_credentials,
    scrubbed_child_environment,
)

SECRET = "sk-unit-test-never-a-real-key"
DIGEST = f"sha256:{'d' * 64}"


def model(credential_env: str = "TECHTREE_MODEL_API_KEY") -> ModelSpec:
    return ModelSpec(
        provider="prime",
        model_id="vendor/small-instruct",
        revision=None,
        credential_env=credential_env,
    )


def engine(tmp_path: Path) -> EngineInstallation:
    return EngineInstallation(
        digest=DIGEST,
        installed_at=datetime(2026, 1, 1, tzinfo=UTC),
        python_executable=str(tmp_path / "engine" / ".venv" / "bin" / "python"),
        descriptor_digest=DIGEST,
        verified=True,
    )


# ---------------------------------------------------------------------------
# Diagnosis
# ---------------------------------------------------------------------------


def test_a_credential_in_the_environment_is_reported_without_its_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TECHTREE_MODEL_API_KEY", SECRET)

    status = credential_status(model())

    assert status.available is True
    assert status.source == "environment"
    assert SECRET not in status.model_dump_json()


def test_an_absent_credential_is_reported_as_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("TECHTREE_MODEL_API_KEY", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))

    status = credential_status(model())

    assert status.available is False
    assert status.source == "missing"


def test_an_empty_credential_counts_as_absent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("TECHTREE_MODEL_API_KEY", "")
    monkeypatch.setenv("HOME", str(tmp_path))

    assert credential_status(model()).available is False


def test_only_a_prime_named_credential_falls_back_to_the_prime_configuration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    prime_config = tmp_path / ".prime" / "config.json"
    prime_config.parent.mkdir(parents=True)
    prime_config.write_text(json.dumps({"api_key": SECRET}))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv(PRIME_CREDENTIAL_ENV, raising=False)
    monkeypatch.delenv("TECHTREE_MODEL_API_KEY", raising=False)

    prime = credential_status(model(PRIME_CREDENTIAL_ENV))
    other = credential_status(model("TECHTREE_MODEL_API_KEY"))

    assert prime.available is True
    assert prime.source == "prime_config"
    assert SECRET not in prime.model_dump_json()
    # A differently named credential is an ordinary environment variable; the
    # pinned client gives its own resolution only to PRIME_API_KEY.
    assert other.available is False


def test_a_missing_credential_refuses_with_actions_that_name_the_variable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("TECHTREE_MODEL_API_KEY", raising=False)

    with pytest.raises(AuthenticationError) as caught:
        require_credentials(model())

    error = caught.value
    assert error.code == "model_credentials_missing"
    assert error.details["credential_env"] == "TECHTREE_MODEL_API_KEY"
    assert any(
        "TECHTREE_MODEL_API_KEY" in action.label for action in error.next_actions
    )


def test_the_refusal_says_this_is_not_the_operators_own_sign_in(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Spec sections 6.9 and 6.18 keep evaluation auth and host auth apart, and
    # the message is the only place a person meets that distinction.
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("TECHTREE_MODEL_API_KEY", raising=False)

    detail = credential_status(model()).detail

    assert "subject" in detail
    assert "your own agent" in detail


# ---------------------------------------------------------------------------
# The child environment
# ---------------------------------------------------------------------------


def test_the_child_inherits_nothing_the_allow_list_does_not_name(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "not-this-one")
    monkeypatch.setenv("OPENAI_API_KEY", "nor-this-one")
    monkeypatch.setenv("TECHTREE_MODEL_API_KEY", SECRET)

    environment = scrubbed_child_environment(model=model(), engine=engine(tmp_path))

    assert "AWS_SECRET_ACCESS_KEY" not in environment
    assert "OPENAI_API_KEY" not in environment
    assert environment["TECHTREE_MODEL_API_KEY"] == SECRET


def test_the_child_gets_no_credential_when_the_host_has_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("TECHTREE_MODEL_API_KEY", raising=False)

    environment = scrubbed_child_environment(model=model(), engine=engine(tmp_path))

    assert "TECHTREE_MODEL_API_KEY" not in environment


def test_the_engines_own_executables_come_first_on_the_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    installation = engine(tmp_path)

    environment = scrubbed_child_environment(model=model(), engine=installation)

    first = environment["PATH"].split(":")[0]
    assert first == str(Path(installation.python_executable).parent)
    assert "/usr/bin" in environment["PATH"]


def test_prime_routing_variables_are_forwarded_but_nothing_else_prime(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PRIME_TEAM_ID", "team-42")
    monkeypatch.setenv("PRIME_INFERENCE_URL", "https://api.pinference.ai/api/v1")
    monkeypatch.setenv("PRIME_SOMETHING_ELSE", "no")

    environment = scrubbed_child_environment(model=model(), engine=engine(tmp_path))

    assert environment["PRIME_TEAM_ID"] == "team-42"
    assert environment["PRIME_INFERENCE_URL"].endswith("/api/v1")
    assert "PRIME_SOMETHING_ELSE" not in environment


def test_a_redacted_environment_hides_secrets_and_keeps_the_rest_readable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("TECHTREE_MODEL_API_KEY", SECRET)
    monkeypatch.setenv("PATH", "/usr/bin")
    environment = scrubbed_child_environment(model=model(), engine=engine(tmp_path))

    described = redacted_environment(
        environment, secret_names=["TECHTREE_MODEL_API_KEY"]
    )

    assert SECRET not in json.dumps(described)
    assert str(len(SECRET)) in described["TECHTREE_MODEL_API_KEY"]
    assert "/usr/bin" in described["PATH"]
