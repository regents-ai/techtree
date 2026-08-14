"""Strict parsing of everything that crosses into the plugin.

Specification section 7.4: unknown schema versions, unknown fields, shell
strings, and unbounded values are rejected rather than repaired.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from techtree_hermes.errors import (
    BootstrapPlanError,
    CliEnvelopeError,
    PluginError,
    scrub_text,
)
from techtree_hermes.models import (
    parse_bootstrap_install_plan,
    parse_cli_envelope,
    parse_release_core,
)
from techtree_hermes.release import (
    load_embedded_release_core,
    release_core_digest,
)

VALID_RELEASE_CORE: dict[str, Any] = {
    "schema_version": "techtree.release-core.v1",
    "placeholder_release": False,
    "placeholder_fields": [],
    "release_id": "test-release",
    "cli_version": "0.1.0",
    "cli_source_commit": "a" * 40,
    "protocol_version": "v1alpha1",
    "engine_digest": "sha256:" + "1" * 64,
    "catalog_digest": "sha256:" + "2" * 64,
    "intro_climb_reference": "hello-world-climb@1",
    "starter_skill_digest": "sha256:" + "3" * 64,
    "skill_improver_digest": "sha256:" + "5" * 64,
    "minimum_host_hermes_version": "0.20.0",
    "maximum_tested_host_hermes_version": "0.20.0",
    "subject_hermes_version": "0.20.0",
}

#: The digest the release above is published under, taken over its one stored
#: spelling. A change here means the release document contract changed.
RELEASE_DIGEST_GOLDEN = (
    "sha256:42325d452e435b7324b5c4a1952c38b5d4e2a9e0eaa3b6df087b9dea94d24bfb"
)

VALID_ENVELOPE: dict[str, Any] = {
    "schema_version": "techtree.cli.v1",
    "command": "doctor",
    "ok": True,
    "data": {"checks": []},
    "error": None,
    "messages": [],
    "warnings": [],
    "next_actions": [],
}

VALID_PLAN: dict[str, Any] = {
    "plan_id": "install_" + "0" * 32,
    "package": "techtree",
    "version": "0.1.0",
    "argv": ["uv", "tool", "install", "techtree==0.1.0"],
    "release_core_digest": "sha256:" + "6" * 64,
    "requires_confirmation": True,
    "created_at": "2026-08-13T00:00:00Z",
    "expires_at": "2026-08-13T00:15:00Z",
}


def _release_bytes(**overrides: Any) -> bytes:
    document = {**VALID_RELEASE_CORE, **overrides}
    for key, value in overrides.items():
        if value is None:
            del document[key]
    return json.dumps(document).encode("utf-8")


# Release ----------------------------------------------------------------------


def test_a_complete_release_parses() -> None:
    core = parse_release_core(_release_bytes())

    assert core.release_id == "test-release"
    assert core.cli_version == "0.1.0"


def test_the_release_digest_does_not_depend_on_how_the_file_was_written() -> None:
    """Two writers of the same release agree, because the spelling is one."""
    shuffled = dict(reversed(list(VALID_RELEASE_CORE.items())))

    first = release_core_digest(parse_release_core(_release_bytes()))
    second = release_core_digest(
        parse_release_core(json.dumps(shuffled).encode("utf-8"))
    )

    assert first == second
    assert first == RELEASE_DIGEST_GOLDEN


def test_the_embedded_release_is_valid() -> None:
    core = load_embedded_release_core()

    assert core.schema_version == "techtree.release-core.v1"
    assert release_core_digest(core).startswith("sha256:")


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"schema_version": "techtree.release-core.v2"}, "schema version"),
        ({"engine_digest": "not-a-digest"}, "sha256 digest"),
        ({"cli_source_commit": "abc"}, "40-character commit"),
        ({"intro_climb_reference": "hello-world-climb"}, "slug@version"),
        ({"cli_version": ""}, "non-empty string"),
        ({"cli_version": None}, "missing fields"),
        ({"upload_endpoint": "https://example.test"}, "unknown fields"),
    ],
)
def test_a_release_that_breaks_the_contract_is_rejected(
    overrides: dict[str, Any], expected: str
) -> None:
    with pytest.raises(PluginError, match=expected) as raised:
        parse_release_core(_release_bytes(**overrides))

    assert raised.value.code == "plugin_release_core_invalid"


def test_release_bytes_that_are_not_json_are_rejected() -> None:
    with pytest.raises(PluginError):
        parse_release_core(b"not json at all")


# CLI envelopes ----------------------------------------------------------------


def test_one_envelope_parses() -> None:
    parsed = parse_cli_envelope(json.dumps(VALID_ENVELOPE))

    assert parsed["command"] == "doctor"
    assert parsed["ok"] is True


def test_two_json_records_are_a_contract_failure() -> None:
    stream = json.dumps(VALID_ENVELOPE) + "\n" + json.dumps(VALID_ENVELOPE)

    with pytest.raises(CliEnvelopeError, match="exactly one JSON document"):
        parse_cli_envelope(stream)


def test_ansi_in_machine_output_is_a_contract_failure() -> None:
    coloured = "\x1b[32m" + json.dumps(VALID_ENVELOPE) + "\x1b[0m"

    with pytest.raises(CliEnvelopeError, match="ANSI"):
        parse_cli_envelope(coloured)


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ({"schema_version": "techtree.cli.v2"}, "schema"),
        ({"ok": "yes"}, "'ok'"),
        ({"command": ""}, "command"),
        ({"messages": {}}, "messages"),
    ],
)
def test_a_malformed_envelope_is_rejected(
    mutation: dict[str, Any], expected: str
) -> None:
    with pytest.raises(CliEnvelopeError, match=expected):
        parse_cli_envelope(json.dumps({**VALID_ENVELOPE, **mutation}))


def test_a_truncated_envelope_is_rejected() -> None:
    partial = {key: value for key, value in VALID_ENVELOPE.items() if key != "data"}

    with pytest.raises(CliEnvelopeError, match="missing fields"):
        parse_cli_envelope(json.dumps(partial))


def test_a_field_the_contract_does_not_have_is_rejected() -> None:
    """A newer CLI is a decision for a person, not a silent pass-through."""
    envelope = {**VALID_ENVELOPE, "upload_receipt_url": "https://example.test"}

    with pytest.raises(CliEnvelopeError, match="does not know"):
        parse_cli_envelope(json.dumps(envelope))


@pytest.mark.parametrize(
    ("entry", "expected"),
    [
        ({"level": "info", "text": "hello"}, "missing"),
        ({"level": "shout", "code": None, "text": "hello"}, "level"),
        ({"level": "info", "code": None, "text": ""}, "no text"),
        ({"level": "info", "code": 7, "text": "hello"}, "non-string code"),
    ],
)
def test_a_malformed_message_is_rejected(entry: dict[str, Any], expected: str) -> None:
    with pytest.raises(CliEnvelopeError, match=expected):
        parse_cli_envelope(json.dumps({**VALID_ENVELOPE, "messages": [entry]}))


def _next_action(**overrides: Any) -> dict[str, Any]:
    action: dict[str, Any] = {
        "id": "list_climbs",
        "label": "Browse the available Climbs",
        "reason": "This host is ready.",
        "cli": ["techtree", "climb", "list"],
        "hermes_tool": None,
        "hermes_args": None,
        "requires_user_confirmation": False,
    }
    action.update(overrides)
    return action


def test_a_complete_next_action_is_accepted() -> None:
    envelope = parse_cli_envelope(
        json.dumps({**VALID_ENVELOPE, "next_actions": [_next_action()]})
    )

    assert envelope["next_actions"][0]["id"] == "list_climbs"


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"label": ""}, "no label"),
        ({"requires_user_confirmation": "no"}, "needs confirmation"),
        ({"cli": "techtree climb list"}, "argv list"),
        ({"cli": ["techtree", ""]}, "empty argument"),
    ],
)
def test_a_malformed_next_action_is_rejected(
    overrides: dict[str, Any], expected: str
) -> None:
    action = _next_action(**overrides)

    with pytest.raises(CliEnvelopeError, match=expected):
        parse_cli_envelope(json.dumps({**VALID_ENVELOPE, "next_actions": [action]}))


def test_a_failure_must_carry_its_error() -> None:
    with pytest.raises(CliEnvelopeError, match="failure with no error"):
        parse_cli_envelope(json.dumps({**VALID_ENVELOPE, "ok": False}))


def test_a_success_must_not_carry_an_error() -> None:
    error = {
        "code": "climb_not_found",
        "message": "no such Climb",
        "retryable": False,
        "details": {},
    }

    with pytest.raises(CliEnvelopeError, match="success and an error"):
        parse_cli_envelope(json.dumps({**VALID_ENVELOPE, "error": error}))


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        ({"code": "x", "message": "y", "retryable": False}, "missing"),
        ({"code": "", "message": "y", "retryable": False, "details": {}}, "no code"),
        ({"code": "x", "message": "y", "retryable": "no", "details": {}}, "retryable"),
        ({"code": "x", "message": "y", "retryable": True, "details": []}, "details"),
    ],
)
def test_a_malformed_error_is_rejected(error: dict[str, Any], expected: str) -> None:
    envelope = {**VALID_ENVELOPE, "ok": False, "error": error}

    with pytest.raises(CliEnvelopeError, match=expected):
        parse_cli_envelope(json.dumps(envelope))


# Install plans ----------------------------------------------------------------


def test_a_fixed_plan_parses() -> None:
    plan = parse_bootstrap_install_plan(VALID_PLAN)

    assert plan.argv == ("uv", "tool", "install", "techtree==0.1.0")
    assert plan.requires_confirmation is True
    assert plan.display_command() == "uv tool install techtree==0.1.0"


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ({"command": "uv tool install techtree"}, "executable fields"),
        ({"index_url": "https://example.test/simple"}, "executable fields"),
        ({"argv": "uv tool install techtree==0.1.0"}, "argument array"),
        ({"argv": ["curl", "install", "techtree==0.1.0"]}, "installer must be"),
        ({"argv": ["uv", "tool", "install", "techtree"]}, "does not install exactly"),
        ({"requires_confirmation": False}, "requires confirmation"),
        ({"plan_id": "install_pretty_please"}, "plan identifier"),
        ({"version": "0.1.0; rm -rf /"}, "version string"),
    ],
)
def test_a_plan_that_could_run_something_else_is_rejected(
    mutation: dict[str, Any], expected: str
) -> None:
    with pytest.raises(BootstrapPlanError, match=expected):
        parse_bootstrap_install_plan({**VALID_PLAN, **mutation})


# Scrubbing --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "leaked"),
    [
        ("Authorization: Bearer abc123DEF456ghi", "abc123DEF456ghi"),
        ('{"api_key": "sk-live-secret-value"}', "sk-live-secret-value"),
        ("OPENAI_API_KEY=sk-proj-abcdefghijklmnop", "sk-proj-abcdefghijklmnop"),
        ("token ghp_abcdefghijklmnopqrstuvwxyz012345", "ghp_abcdefghijklmnop"),
        (
            "-----BEGIN PRIVATE KEY-----\nMIIBVgIBADAN\n-----END PRIVATE KEY-----",
            "MIIBVgIBADAN",
        ),
    ],
)
def test_secrets_never_survive_scrubbing(text: str, leaked: str) -> None:
    scrubbed = scrub_text(text)

    assert leaked not in scrubbed
    assert "redacted" in scrubbed


def test_scrubbing_leaves_ordinary_diagnostics_alone() -> None:
    message = "run run_0123456789abcdef0123456789abcdef failed: engine not verified"

    assert scrub_text(message) == message
