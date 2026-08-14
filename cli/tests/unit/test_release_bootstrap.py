"""The website wrapper, checked from the side that produced the release.

Spec sections 9.3.2, 9.4 and 9.7.

The bootstrap document and the ReleaseCore repeat four coordinates, and the
whole point of checking them here is that a repeat which drifts sends operators
to install one thing while the CLI believes another. Each repeat is broken on
its own below.

The shape rules are the website's. They are restated in these tests for the
same reason they are restated in the checker: a release that the website would
refuse should fail while it is being assembled, not at deploy time.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from techtree.release.bootstrap import (
    BOOTSTRAP_RELEASE_INVALID,
    BOOTSTRAP_RELEASE_MISMATCH,
    verify_bootstrap_document,
)
from techtree.release.checks import ReleaseCheck, ReleaseVerification
from techtree.release.models import (
    PLACEHOLDER_COMMIT,
    PLACEHOLDER_DIGEST,
    PLACEHOLDER_OBJECT_URL,
    PLACEHOLDER_VERSION,
    ReleaseCore,
)

INTRO_CLIMB = "hello-world-climb@1"
PLUGIN_COMMIT = "e" * 40
STARTER_OBJECT_URL = "https://techtree.sh/objects/hello-world-starter-v1/SKILL.md"


def core(**overrides: Any) -> ReleaseCore:
    """Return the placeholder release this build currently carries."""
    fields: dict[str, Any] = {
        "schema_version": "techtree.release-core.v1",
        "placeholder_release": True,
        "placeholder_fields": [
            "cli_source_commit",
            "cli_version",
            "maximum_tested_host_hermes_version",
            "release_id",
            "skill_improver_digest",
            "starter_skill_digest",
            "starter_skill_object_url",
        ],
        "release_id": PLACEHOLDER_VERSION,
        "cli_version": PLACEHOLDER_VERSION,
        "cli_source_commit": PLACEHOLDER_COMMIT,
        "protocol_version": "v1alpha1",
        "engine_digest": "sha256:" + "1a" * 32,
        "catalog_digest": "sha256:" + "2b" * 32,
        "intro_climb_reference": INTRO_CLIMB,
        "starter_skill_digest": PLACEHOLDER_DIGEST,
        "starter_skill_object_url": PLACEHOLDER_OBJECT_URL,
        "skill_improver_digest": PLACEHOLDER_DIGEST,
        "minimum_host_hermes_version": "0.19.0",
        "maximum_tested_host_hermes_version": PLACEHOLDER_VERSION,
        "subject_hermes_version": "0.19.0",
    }
    return ReleaseCore(**{**fields, **overrides})


def bootstrap(**overrides: Any) -> dict[str, Any]:
    """Return a bootstrap document that agrees with :func:`core` completely.

    Its shape is the one the website publishes today, so a change on either
    side of the boundary shows up here as a failing test rather than as a
    release that cannot be deployed.
    """
    document: dict[str, Any] = {
        "schema_version": "techtree.bootstrap.v1alpha1",
        "channel": "development",
        "placeholder_release": True,
        "published_at": "2026-08-13T00:00:00Z",
        "minimums": {
            "hermes_version": "0.19.0",
            "python": "3.12",
            "uv": "0.11.1",
            "docker_required": True,
        },
        "cli": {
            "distribution": "techtree",
            "version": PLACEHOLDER_VERSION,
            "source_revision": PLACEHOLDER_COMMIT,
            "install_argv": [
                "uv",
                "tool",
                "install",
                f"techtree=={PLACEHOLDER_VERSION}",
            ],
        },
        "hermes_plugin": {
            "plugin_id": "techtree",
            "repository": "regents-labs/techtree-hermes",
            "revision": PLACEHOLDER_COMMIT,
            "install_argv": [
                "hermes",
                "plugins",
                "install",
                "regents-labs/techtree-hermes",
                "--ref",
                PLACEHOLDER_COMMIT,
                "--enable",
            ],
            "doctor_argv": ["hermes", "plugins", "doctor", "techtree", "--ci"],
        },
        "introductory_climb": {
            "reference": INTRO_CLIMB,
            "host_prompt": "Set up Techtree and run the introductory Climb.",
        },
        "starter_skill": {
            "name": "hello-world-starter-v1",
            "object_url": PLACEHOLDER_OBJECT_URL,
            "digest": PLACEHOLDER_DIGEST,
        },
    }
    return {**document, **overrides}


def check(
    document: dict[str, Any], release: ReleaseCore | None = None
) -> ReleaseVerification:
    """Verify a bootstrap document against a release."""
    return verify_bootstrap_document(
        release or core(), json.dumps(document).encode("utf-8")
    )


def by_id(result: ReleaseVerification) -> dict[str, ReleaseCheck]:
    """Return every check the verification ran, keyed by its identifier."""
    return {item.id: item for item in result.checks}


def assert_only_failure(
    result: ReleaseVerification, identifier: str, code: str
) -> None:
    """Assert exactly one check failed, that it is this one, and why."""
    assert [item.id for item in result.failures] == [identifier]
    assert by_id(result)[identifier].code == code


def replacing(section: str, **changes: Any) -> dict[str, Any]:
    """Return a bootstrap document with one nested section altered."""
    document = bootstrap()
    document[section] = {**document[section], **changes}
    return document


# ---------------------------------------------------------------------------
# The agreeing case
# ---------------------------------------------------------------------------


def test_a_wrapper_that_names_this_release_verifies() -> None:
    result = check(bootstrap())
    assert result.verified is True
    assert set(by_id(result)) == {
        "bootstrap_schema_version",
        "bootstrap_importer_contract",
        "bootstrap_placeholder_declaration",
        "bootstrap_cli_version",
        "bootstrap_cli_source_revision",
        "bootstrap_hermes_minimum",
        "bootstrap_intro_climb",
        "bootstrap_starter_skill_object_url",
        "bootstrap_starter_skill_digest",
        "bootstrap_cli_install_argv",
        "bootstrap_plugin_install_argv",
    }


# ---------------------------------------------------------------------------
# One drifted coordinate at a time
# ---------------------------------------------------------------------------


def test_a_wrapper_naming_another_cli_version_fails_alone() -> None:
    """The install command is checked against the release, not against itself.

    So a wrapper that advertises one version while still publishing the
    release's own install command breaks exactly one claim, and the command it
    publishes stays correct.
    """
    result = check(replacing("cli", version="0.1.0"))
    assert_only_failure(result, "bootstrap_cli_version", BOOTSTRAP_RELEASE_MISMATCH)


def test_a_wrapper_naming_another_source_commit_fails_alone() -> None:
    result = check(replacing("cli", source_revision="a" * 40))
    assert_only_failure(
        result, "bootstrap_cli_source_revision", BOOTSTRAP_RELEASE_MISMATCH
    )


def test_a_wrapper_naming_another_hermes_minimum_fails_alone() -> None:
    result = check(replacing("minimums", hermes_version="0.20.0"))
    assert_only_failure(result, "bootstrap_hermes_minimum", BOOTSTRAP_RELEASE_MISMATCH)


def test_a_wrapper_naming_another_climb_fails_alone() -> None:
    result = check(replacing("introductory_climb", reference="something-else@1"))
    assert_only_failure(result, "bootstrap_intro_climb", BOOTSTRAP_RELEASE_MISMATCH)


def test_a_wrapper_serving_the_starter_skill_elsewhere_fails_alone() -> None:
    """Spec section 10.5: the wrapper says where the public Skill object is."""
    result = check(replacing("starter_skill", object_url=STARTER_OBJECT_URL))
    assert_only_failure(
        result, "bootstrap_starter_skill_object_url", BOOTSTRAP_RELEASE_MISMATCH
    )


def test_a_wrapper_naming_another_starter_skill_fails_alone() -> None:
    """An address the release agrees with, over bytes it never measured."""
    result = check(replacing("starter_skill", digest="sha256:" + "7a" * 32))
    assert_only_failure(
        result, "bootstrap_starter_skill_digest", BOOTSTRAP_RELEASE_MISMATCH
    )


def test_a_wrapper_that_publishes_no_starter_skill_at_all_is_refused() -> None:
    """The coordinate is required, so an omitted section is a shape failure."""
    document = bootstrap()
    del document["starter_skill"]
    result = check(document)
    assert_only_failure(
        result, "bootstrap_importer_contract", BOOTSTRAP_RELEASE_INVALID
    )
    assert "starter_skill.object_url must be an object URL" in result.failures[0].detail
    assert "starter_skill.digest must be a digest" in result.failures[0].detail


@pytest.mark.parametrize(
    "value",
    [
        "techtree.sh/SKILL.md",
        "http://techtree.sh/SKILL.md",
        "https://techtree.sh",
        "",
        "https://user:token@techtree.sh/SKILL.md",
    ],
)
def test_an_address_that_is_not_one_exact_object_is_refused(value: str) -> None:
    """Decision 0007 R10: concrete and immutable, or the release is not real.

    A credential in the authority is refused on both sides of the boundary: the
    website would be publishing it to everyone who reads the wrapper.
    """
    result = check(replacing("starter_skill", object_url=value))
    assert_only_failure(
        result, "bootstrap_importer_contract", BOOTSTRAP_RELEASE_INVALID
    )


def test_an_install_command_that_does_not_pin_the_version_fails_alone() -> None:
    result = check(replacing("cli", install_argv=["uv", "tool", "install", "techtree"]))
    assert_only_failure(
        result, "bootstrap_cli_install_argv", BOOTSTRAP_RELEASE_MISMATCH
    )


def test_a_plugin_command_that_does_not_pin_the_commit_fails_alone() -> None:
    result = check(
        replacing(
            "hermes_plugin",
            install_argv=[
                "hermes",
                "plugins",
                "install",
                "regents-labs/techtree-hermes",
            ],
        )
    )
    assert_only_failure(
        result, "bootstrap_plugin_install_argv", BOOTSTRAP_RELEASE_MISMATCH
    )


def test_a_wrapper_for_a_different_schema_is_refused_before_anything_else() -> None:
    result = check(bootstrap(schema_version="techtree.bootstrap.v2"))
    assert [item.id for item in result.checks] == ["bootstrap_schema_version"]
    assert result.failures[0].code == BOOTSTRAP_RELEASE_INVALID


# ---------------------------------------------------------------------------
# The placeholder declaration is mandatory on both sides
# ---------------------------------------------------------------------------


def test_a_wrapper_that_forgets_to_declare_itself_is_refused() -> None:
    document = bootstrap()
    del document["placeholder_release"]
    result = check(document)
    assert_only_failure(
        result, "bootstrap_importer_contract", BOOTSTRAP_RELEASE_INVALID
    )
    assert "placeholder_release must be a boolean" in result.failures[0].detail


def test_a_declaration_that_is_not_a_boolean_is_refused() -> None:
    result = check(bootstrap(placeholder_release="true"))
    assert_only_failure(
        result, "bootstrap_importer_contract", BOOTSTRAP_RELEASE_INVALID
    )


def test_a_real_wrapper_over_a_placeholder_release_is_refused() -> None:
    result = check(bootstrap(placeholder_release=False))
    assert_only_failure(
        result, "bootstrap_placeholder_declaration", BOOTSTRAP_RELEASE_MISMATCH
    )


def test_a_placeholder_wrapper_over_a_real_release_is_refused() -> None:
    real = core(
        placeholder_release=False,
        placeholder_fields=[],
        release_id="climb-v0.1.0",
        cli_version="0.1.0",
        cli_source_commit="f" * 40,
        maximum_tested_host_hermes_version="0.19.3",
        skill_improver_digest="sha256:" + "5e" * 32,
        starter_skill_digest="sha256:" + "6f" * 32,
        starter_skill_object_url=STARTER_OBJECT_URL,
    )
    document = replacing(
        "cli",
        version="0.1.0",
        source_revision="f" * 40,
        install_argv=["uv", "tool", "install", "techtree==0.1.0"],
    )
    document["starter_skill"] = {
        **document["starter_skill"],
        "object_url": STARTER_OBJECT_URL,
        "digest": "sha256:" + "6f" * 32,
    }
    result = check(document, real)
    assert_only_failure(
        result, "bootstrap_placeholder_declaration", BOOTSTRAP_RELEASE_MISMATCH
    )


# ---------------------------------------------------------------------------
# The website's own shape rules
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("section", "field"),
    [
        ("cli", "distribution"),
        ("cli", "version"),
        ("cli", "install_argv"),
        ("hermes_plugin", "plugin_id"),
        ("hermes_plugin", "revision"),
        ("hermes_plugin", "doctor_argv"),
        ("introductory_climb", "host_prompt"),
        ("minimums", "hermes_version"),
    ],
)
def test_every_field_the_website_requires_is_required_here(
    section: str, field: str
) -> None:
    document = bootstrap()
    del document[section][field]
    result = check(document)
    assert_only_failure(
        result, "bootstrap_importer_contract", BOOTSTRAP_RELEASE_INVALID
    )
    assert f"{section}.{field}" in result.failures[0].detail


def test_a_shell_command_string_is_not_an_argument_array() -> None:
    result = check(replacing("cli", install_argv="uv tool install techtree"))
    assert_only_failure(
        result, "bootstrap_importer_contract", BOOTSTRAP_RELEASE_INVALID
    )
    assert "cli.install_argv must be an argument array" in result.failures[0].detail


def test_an_empty_argument_array_is_refused() -> None:
    result = check(replacing("hermes_plugin", doctor_argv=[]))
    assert_only_failure(
        result, "bootstrap_importer_contract", BOOTSTRAP_RELEASE_INVALID
    )


def test_an_abbreviated_plugin_commit_is_refused() -> None:
    result = check(replacing("hermes_plugin", revision="e" * 12))
    assert_only_failure(
        result, "bootstrap_importer_contract", BOOTSTRAP_RELEASE_INVALID
    )


def test_a_published_time_that_is_not_an_instant_is_refused() -> None:
    result = check(bootstrap(published_at="yesterday"))
    assert_only_failure(
        result, "bootstrap_importer_contract", BOOTSTRAP_RELEASE_INVALID
    )


def test_a_document_that_is_not_json_is_refused() -> None:
    result = verify_bootstrap_document(core(), b"not json")
    assert result.verified is False
    assert result.failures[0].id == "bootstrap_document"


def test_a_json_array_is_not_a_bootstrap_document() -> None:
    result = verify_bootstrap_document(core(), b"[]")
    assert result.verified is False
    assert result.failures[0].id == "bootstrap_document"


def test_a_plugin_commit_is_never_compared_against_the_release() -> None:
    """A ReleaseCore names no plugin commit, so nothing here may claim one."""
    result = check(
        replacing(
            "hermes_plugin",
            revision=PLUGIN_COMMIT,
            install_argv=[
                "hermes",
                "plugins",
                "install",
                "regents-labs/techtree-hermes",
                "--ref",
                PLUGIN_COMMIT,
                "--enable",
            ],
        )
    )
    assert result.verified is True
