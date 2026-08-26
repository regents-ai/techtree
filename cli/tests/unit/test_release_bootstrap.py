"""The website wrapper, checked from the side that produced the release.

Spec sections 9.3.2, 9.4 and 9.7; decisions document 0026.

The bootstrap document and the ReleaseCore repeat four coordinates, and the
whole point of checking them here is that a repeat which drifts sends operators
to install one thing while the CLI believes another. Each repeat is broken on
its own below.

The document also names the source commit of the published wheel, which the
release document deliberately does not carry. That one is checked against the
wheel's own stamp, because the artifact is the only thing that can confirm it.

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
from techtree.release.models import ReleaseCore
from techtree.release.provenance import BuildProvenance

INTRO_CLIMB = "hello-world-climb@1"
PLUGIN_COMMIT = "e" * 40
WHEEL_COMMIT = "b" * 40
STARTER_FILE_DIGEST = "sha256:" + "3c" * 32
STARTER_TREE_DIGEST = "sha256:" + "4d" * 32
STARTER_OBJECT_URL = f"https://techtree.sh/api/v1/objects/{STARTER_FILE_DIGEST}"
OTHER_FILE_DIGEST = "sha256:" + "7a" * 32
OTHER_OBJECT_URL = f"https://techtree.sh/api/v1/objects/{OTHER_FILE_DIGEST}"


def core(**overrides: Any) -> ReleaseCore:
    """Return the release this build carries, every coordinate concrete."""
    fields: dict[str, Any] = {
        "schema_version": "techtree.release-core.v1",
        "release_id": "climb-v0.1.0",
        "cli_version": "0.1.0",
        "protocol_version": "v1alpha1",
        "engine_digest": "sha256:" + "1a" * 32,
        "catalog_digest": "sha256:" + "2b" * 32,
        "intro_climb_reference": INTRO_CLIMB,
        "starter_skill_digest": STARTER_TREE_DIGEST,
        "starter_skill_object_url": STARTER_OBJECT_URL,
        "skill_improver_digest": "sha256:" + "5e" * 32,
        "minimum_host_hermes_version": "0.19.0",
        "maximum_tested_host_hermes_version": "0.19.3",
        "subject_hermes_version": "0.19.0",
    }
    return ReleaseCore(**{**fields, **overrides})


def wheel(commit: str = WHEEL_COMMIT) -> BuildProvenance:
    """Return the stamp a published wheel carries."""
    return BuildProvenance(
        schema_version="techtree.build-provenance.v1", source_commit=commit
    )


def bootstrap(**overrides: Any) -> dict[str, Any]:
    """Return a bootstrap document that agrees with :func:`core` completely.

    Its shape is the one the website publishes today, so a change on either
    side of the boundary shows up here as a failing test rather than as a
    release that cannot be deployed.
    """
    document: dict[str, Any] = {
        "schema_version": "techtree.bootstrap.v1alpha1",
        "channel": "development",
        "placeholder_release": False,
        "published_at": "2026-08-13T00:00:00Z",
        "minimums": {
            "hermes_version": "0.19.0",
            "python": "3.12",
            "uv": "0.11.1",
            "docker_required": True,
        },
        "cli": {
            "distribution": "techtree",
            "version": "0.1.0",
            "source_revision": WHEEL_COMMIT,
            "wheel_sha256": f"sha256:{WHEEL_SHA256}",
            "install_argv": [
                "uv",
                "tool",
                "install",
                "--python",
                "3.12",
                "techtree==0.1.0",
            ],
        },
        "hermes_plugin": {
            "plugin_id": "techtree",
            "repository": "regents-labs/techtree-hermes",
            "revision": PLUGIN_COMMIT,
            "install_argv": [
                "hermes",
                "plugins",
                "install",
                "regents-labs/techtree-hermes",
                "--ref",
                PLUGIN_COMMIT,
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
            "object_url": STARTER_OBJECT_URL,
            "file_digest": STARTER_FILE_DIGEST,
            "tree_digest": STARTER_TREE_DIGEST,
            "media_type": "text/markdown",
            "size": 1496,
        },
    }
    return {**document, **overrides}


#: The SHA-256 of the wheel these tests pretend to have built, as the
#: caller computes it: lowercase hex, no prefix.
WHEEL_SHA256 = "b" * 64


def check(
    document: dict[str, Any],
    release: ReleaseCore | None = None,
    stamp: BuildProvenance | None = None,
    wheel_sha256: str = WHEEL_SHA256,
) -> ReleaseVerification:
    """Verify a bootstrap document against a release and a built wheel."""
    return verify_bootstrap_document(
        release or core(),
        json.dumps(document).encode("utf-8"),
        wheel=stamp or wheel(),
        wheel_sha256=wheel_sha256,
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
        "bootstrap_cli_version",
        "bootstrap_cli_source_revision",
        "bootstrap_cli_wheel_sha256",
        "bootstrap_hermes_minimum",
        "bootstrap_intro_climb",
        "bootstrap_starter_skill_object_url",
        "bootstrap_starter_skill_tree_digest",
        "bootstrap_starter_skill_address",
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
    result = check(replacing("cli", version="0.2.0"))
    assert_only_failure(result, "bootstrap_cli_version", BOOTSTRAP_RELEASE_MISMATCH)


def test_a_wrapper_naming_a_commit_the_wheel_was_not_built_from_fails_alone() -> None:
    """The wheel is the only thing that can confirm which commit it is."""
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
    result = check(
        replacing(
            "starter_skill",
            object_url=OTHER_OBJECT_URL,
            file_digest=OTHER_FILE_DIGEST,
        )
    )
    assert_only_failure(
        result, "bootstrap_starter_skill_object_url", BOOTSTRAP_RELEASE_MISMATCH
    )


def test_a_wrapper_naming_another_starter_skill_fails_alone() -> None:
    """An address the release agrees with, over a tree it never measured."""
    result = check(replacing("starter_skill", tree_digest="sha256:" + "7a" * 32))
    assert_only_failure(
        result, "bootstrap_starter_skill_tree_digest", BOOTSTRAP_RELEASE_MISMATCH
    )


def test_an_address_keyed_by_anything_but_the_bytes_it_returns_fails_alone() -> None:
    """The website files an object under the digest of the file it serves."""
    result = check(replacing("starter_skill", file_digest=OTHER_FILE_DIGEST))
    assert_only_failure(
        result, "bootstrap_starter_skill_address", BOOTSTRAP_RELEASE_MISMATCH
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
    assert "starter_skill.file_digest must be a digest" in result.failures[0].detail
    assert "starter_skill.tree_digest must be a digest" in result.failures[0].detail


@pytest.mark.parametrize(
    "value",
    [
        f"techtree.sh/{STARTER_FILE_DIGEST}",
        f"http://techtree.sh/{STARTER_FILE_DIGEST}",
        "https://techtree.sh",
        "",
        f"https://user:token@techtree.sh/{STARTER_FILE_DIGEST}",
        "https://techtree.sh/objects/SKILL.md",
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
    result = check(
        replacing("cli", install_argv=["uv", "tool", "install", "--python", "3.12"])
    )
    assert_only_failure(
        result, "bootstrap_cli_install_argv", BOOTSTRAP_RELEASE_MISMATCH
    )


def test_an_install_command_that_does_not_pin_the_interpreter_fails_alone() -> None:
    """The published command must land on a Python this release supports.

    Left to choose, the installer takes the machine's default Python, which can
    be newer than Techtree supports: the install succeeds and the operator's
    first Techtree output is Doctor reporting a wrong interpreter (decision
    0031). A document that publishes such a command does not verify.
    """
    result = check(
        replacing("cli", install_argv=["uv", "tool", "install", "techtree==0.1.0"])
    )
    assert_only_failure(
        result, "bootstrap_cli_install_argv", BOOTSTRAP_RELEASE_MISMATCH
    )
    assert "minimums.python is '3.12'" in result.failures[0].detail


def test_an_install_command_pinning_an_undeclared_interpreter_fails() -> None:
    """The pin is only worth anything if it is the declared interpreter.

    This is the failure the check exists for: a document that tells a reader to
    install on one Python while its own requirements name another.
    """
    result = check(
        replacing(
            "cli",
            install_argv=[
                "uv",
                "tool",
                "install",
                "--python",
                "3.14",
                "techtree==0.1.0",
            ],
        )
    )
    assert_only_failure(
        result, "bootstrap_cli_install_argv", BOOTSTRAP_RELEASE_MISMATCH
    )


def test_the_interpreter_pin_follows_what_the_document_requires() -> None:
    """Move the declared Python and the accepted command moves with it."""
    document = bootstrap()
    document["minimums"]["python"] = "3.13"
    document["cli"]["install_argv"] = [
        "uv",
        "tool",
        "install",
        "--python",
        "3.13",
        "techtree==0.1.0",
    ]

    assert check(document).verified is True


def test_a_document_that_states_no_interpreter_publishes_no_pinned_command() -> None:
    """There is nothing to pin the command to, so the command cannot verify."""
    document = bootstrap()
    del document["minimums"]["python"]

    result = check(document)
    assert_only_failure(
        result, "bootstrap_cli_install_argv", BOOTSTRAP_RELEASE_MISMATCH
    )
    assert "minimums.python is None" in result.failures[0].detail


def test_a_flag_and_a_version_that_are_not_adjacent_do_not_pin_anything() -> None:
    """``--python`` takes the argument beside it, so only that one counts."""
    result = check(
        replacing(
            "cli",
            install_argv=[
                "uv",
                "tool",
                "install",
                "--python",
                "techtree==0.1.0",
                "3.12",
            ],
        )
    )
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
# The website's own declaration
# ---------------------------------------------------------------------------


def test_a_wrapper_that_forgets_to_declare_itself_is_refused() -> None:
    """The website states whether it is serving a development bootstrap."""
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
    result = verify_bootstrap_document(
        core(), b"not json", wheel=wheel(), wheel_sha256=WHEEL_SHA256
    )
    assert result.verified is False
    assert result.failures[0].id == "bootstrap_document"


def test_a_json_array_is_not_a_bootstrap_document() -> None:
    result = verify_bootstrap_document(
        core(), b"[]", wheel=wheel(), wheel_sha256=WHEEL_SHA256
    )
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


def test_a_wheel_that_is_not_the_published_one_is_refused() -> None:
    """The document names a digest; the wheel in hand must hash to it.

    Without this the gate would confirm the wheel's commit and its name while
    never once hashing the bytes a participant actually installs.
    """
    result = check(bootstrap(), wheel_sha256="c" * 64)

    assert_only_failure(
        result, "bootstrap_cli_wheel_sha256", BOOTSTRAP_RELEASE_MISMATCH
    )


def test_the_published_wheel_digest_passes() -> None:
    assert by_id(check(bootstrap()))["bootstrap_cli_wheel_sha256"].status == "passed"
