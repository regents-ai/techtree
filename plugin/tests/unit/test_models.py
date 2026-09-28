"""Strict parsing of everything that crosses into the plugin.

Specification section 7.4: unknown schema versions, unknown fields, shell
strings, and unbounded values are rejected rather than repaired.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from techtree_hermes.cli.errors import (
    BootstrapPlanError,
    CliAnswerError,
    PluginError,
)
from techtree_hermes.cli.release import (
    load_embedded_release_core,
    release_core_digest,
    render_release_core,
)
from techtree_hermes.services.models import (
    _RELEASE_CORE_DIGEST_FIELDS,
    RELEASE_CORE_FIELDS,
    parse_bootstrap_install_plan,
    parse_cli_answer,
    parse_release_core,
)

VALID_RELEASE_CORE: dict[str, Any] = {
    "schema_version": "techtree.release-core.v2",
    "release_id": "test-release",
    "cli_version": "0.1.0",
    "protocol_version": "v1alpha1",
    "engine_digest": "sha256:" + "1" * 64,
    "catalog_digest": "sha256:" + "2" * 64,
    "intro_climb_reference": "hello-world-climb@1",
    "starter_skill_digest": "sha256:" + "3" * 64,
    "starter_skill_object_url": "https://objects.example/objects/sha256:" + "4" * 64,
    "minimum_host_hermes_version": "0.21.3",
    "maximum_tested_host_hermes_version": "0.21.3",
    "subject_hermes_version": "v2026.7.20",
    "publication": {
        "submission_endpoint": "https://log.example/api/v1/publications",
        "public_log_url": "https://log.example/runs",
        # The identifier is the digest of the key beside it, which is the
        # rule the parser enforces and the reason a receipt naming a key it
        # does not carry is caught without looking anything up.
        "network_key": {
            "algorithm": "ed25519",
            "key_id": (
                "sha256:630dcd2966c4336691125448bbb25b4ff412a49c"
                "732db2c8abc1b8581bd710dd"
            ),
            "public_key": "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8=",
        },
    },
}

#: The digest the release above is published under, taken over its one stored
#: spelling. A change here means the release document contract changed.
RELEASE_DIGEST_GOLDEN = (
    "sha256:4dbccc05cdfdd2bafd66b84bf96205b5d4a4a76731d4efaaa0486f0a121f19ac"
)

VALID_ANSWER: dict[str, Any] = {
    "climbs": [],
    "count": 0,
    "warnings": [{"id": "development_climb", "text": "a development Climb"}],
    "report": "No Climbs.",
}

VALID_PLAN: dict[str, Any] = {
    "plan_id": "install_" + "0" * 32,
    "package": "regents-cli",
    "version": "1.0.0",
    "argv": ["uv", "tool", "install", "--python", "3.12", "regents-cli==1.0.0"],
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

    assert core.schema_version == "techtree.release-core.v2"
    assert release_core_digest(core).startswith("sha256:")


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"schema_version": "a-release-core"}, "schema version"),
        ({"engine_digest": "not-a-digest"}, "sha256 digest"),
        ({"intro_climb_reference": "hello-world-climb"}, "slug@version"),
        ({"cli_version": ""}, "non-empty string"),
        ({"cli_version": None}, "missing fields"),
        ({"upload_endpoint": "https://example.test"}, "unknown fields"),
        # The starter Skill's address: https only, keyed by the digest of the
        # file it returns, and never with a credential in the authority.
        # Mirrors techtree-python's OBJECT_URL_PATTERN, because the plugin
        # copies these bytes verbatim.
        ({"starter_skill_object_url": "sha256:" + "3" * 64}, "content address"),
        (
            {"starter_skill_object_url": "http://objects.example/sha256:" + "4" * 64},
            "content address",
        ),
        ({"starter_skill_object_url": "https://objects.example"}, "content address"),
        (
            {"starter_skill_object_url": "https://objects.example/starter.md"},
            "content address",
        ),
        (
            {
                "starter_skill_object_url": "https://u:tok@objects.example/sha256:"
                + "4" * 64
            },
            "content address",
        ),
        ({"starter_skill_object_url": None}, "missing fields"),
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


# regents answers -------------------------------------------------------------------


def test_one_answer_parses() -> None:
    assert parse_cli_answer(json.dumps(VALID_ANSWER)) == VALID_ANSWER


def test_two_json_records_are_a_contract_failure() -> None:
    stream = json.dumps(VALID_ANSWER) + "\n" + json.dumps(VALID_ANSWER)

    with pytest.raises(CliAnswerError, match="exactly one JSON document"):
        parse_cli_answer(stream)


def test_ansi_in_machine_output_is_a_contract_failure() -> None:
    coloured = "\x1b[32m" + json.dumps(VALID_ANSWER) + "\x1b[0m"

    with pytest.raises(CliAnswerError, match="ANSI"):
        parse_cli_answer(coloured)


def test_an_answer_that_is_not_an_object_is_rejected() -> None:
    with pytest.raises(CliAnswerError, match="not a JSON object"):
        parse_cli_answer(json.dumps([VALID_ANSWER]))


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ({"report": ["No Climbs."]}, "report"),
        ({"warnings": {}}, "warnings"),
        ({"warnings": [{"id": "x"}]}, "warning"),
    ],
)
def test_a_malformed_answer_is_rejected(
    mutation: dict[str, Any], expected: str
) -> None:
    with pytest.raises(CliAnswerError, match=expected):
        parse_cli_answer(json.dumps({**VALID_ANSWER, **mutation}))


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ({"error": {"code": "x", "message": "y"}, "count": 0}, "beside 'error'"),
        ({"error": "climb_not_found"}, "not an object"),
        ({"error": {"code": "", "message": "y"}}, "no code"),
        ({"error": {"code": "x", "message": ""}}, "no message"),
        ({"error": {"code": "x", "message": "y", "details": []}}, "details"),
    ],
)
def test_a_malformed_failure_is_rejected(answer: dict[str, Any], expected: str) -> None:
    with pytest.raises(CliAnswerError, match=expected):
        parse_cli_answer(json.dumps(answer))


# Install plans ----------------------------------------------------------------


def test_a_fixed_plan_parses() -> None:
    plan = parse_bootstrap_install_plan(VALID_PLAN)

    assert plan.argv == (
        "uv",
        "tool",
        "install",
        "--python",
        "3.12",
        "regents-cli==1.0.0",
    )
    assert plan.requires_confirmation is True
    assert plan.display_command() == "uv tool install --python 3.12 regents-cli==1.0.0"


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ({"command": "uv tool install regents-cli"}, "executable fields"),
        ({"index_url": "https://example.test/simple"}, "executable fields"),
        (
            {"argv": "uv tool install --python 3.12 regents-cli==1.0.0"},
            "argument array",
        ),
        ({"argv": ["curl", "install", "regents-cli==1.0.0"]}, "installer must be"),
        (
            {"argv": ["uv", "tool", "install", "regents-cli"]},
            "does not install exactly",
        ),
        ({"requires_confirmation": False}, "requires confirmation"),
        ({"plan_id": "install_pretty_please"}, "plan identifier"),
        ({"version": "1.0.0; rm -rf /"}, "version string"),
    ],
)
def test_a_plan_that_could_run_something_else_is_rejected(
    mutation: dict[str, Any], expected: str
) -> None:
    with pytest.raises(BootstrapPlanError, match=expected):
        parse_bootstrap_install_plan({**VALID_PLAN, **mutation})


# Borrowed error detail ------------------------------------------------------------


def test_an_error_is_relayed_unchanged() -> None:
    """Decision 0036: regents' own words about a failure are the ones relayed.

    ``details`` is free-shaped — built from whatever went wrong, often a
    subprocess quoting its own command line back — and it crosses this
    boundary exactly as it arrived.
    """
    error = {
        "code": "engine_install_failed",
        "message": "the engine could not be installed",
        "details": {
            "detail": "uv sync --index-url https://pypi.internal/simple failed",
            "environment": ["HOME=/tmp/home"],
            "nested": {"header": "Accept: application/json"},
            "exit_code": 2,
        },
    }
    raw = json.dumps({"error": error})

    assert parse_cli_answer(raw)["error"] == error


# The starter Skill's two halves ------------------------------------------------------


def test_the_starter_url_is_carried_but_is_not_a_digest() -> None:
    """It is one half of a coordinate, and it is not hashed like the other."""
    core = parse_release_core(_release_bytes())

    assert (
        core.starter_skill_object_url == VALID_RELEASE_CORE["starter_skill_object_url"]
    )
    assert "starter_skill_object_url" in RELEASE_CORE_FIELDS
    assert "starter_skill_object_url" not in _RELEASE_CORE_DIGEST_FIELDS


def test_the_release_round_trips_through_its_one_spelling() -> None:
    """A field added to the roster must survive to_dict and back."""
    core = parse_release_core(_release_bytes())

    assert parse_release_core(render_release_core(core)) == core
    assert (
        core.to_dict()["starter_skill_object_url"]
        == (VALID_RELEASE_CORE["starter_skill_object_url"])
    )
