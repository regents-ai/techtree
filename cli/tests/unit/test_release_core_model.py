"""The ReleaseCore document and its placeholder declaration. Spec section 6.6.

The declaration is the only thing standing between a half-finished release and
a document that reads as a finished one, so these tests attack it from both
sides: a release that hides a blank, and a release that pretends to have one.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError as PydanticValidationError

from techtree.errors import ValidationError
from techtree.release.document import (
    document_digest,
    is_canonical_document,
    parse_release_core,
    render_document,
    render_release_core,
)
from techtree.release.models import (
    PLACEHOLDER_COMMIT,
    PLACEHOLDER_DIGEST,
    PLACEHOLDER_VERSION,
    ReleaseCore,
    ReleaseInputs,
    declared_placeholder_fields,
)

REAL_DIGEST = "sha256:" + "a1" * 32
OTHER_DIGEST = "sha256:" + "b2" * 32
REAL_COMMIT = "c" * 40


def bound_fields() -> dict[str, Any]:
    """Return a ReleaseCore with every coordinate bound to a real value."""
    return {
        "schema_version": "techtree.release-core.v1",
        "placeholder_release": False,
        "placeholder_fields": [],
        "release_id": "climb-v0.1.0",
        "cli_version": "0.1.0",
        "cli_source_commit": REAL_COMMIT,
        "protocol_version": "v1alpha1",
        "engine_digest": REAL_DIGEST,
        "catalog_digest": OTHER_DIGEST,
        "intro_climb_reference": "hello-world-climb@1",
        "starter_skill_digest": REAL_DIGEST,
        "skill_improver_digest": REAL_DIGEST,
        "minimum_host_hermes_version": "0.19.0",
        "maximum_tested_host_hermes_version": "0.19.3",
        "subject_hermes_version": "0.19.0",
    }


def core(**overrides: Any) -> ReleaseCore:
    """Build a ReleaseCore, overriding any field."""
    return ReleaseCore(**{**bound_fields(), **overrides})


def test_a_fully_bound_release_declares_no_placeholders() -> None:
    assert core().placeholder_release is False
    assert core().placeholder_fields == []


def test_a_placeholder_must_be_declared() -> None:
    with pytest.raises(PydanticValidationError, match="must name exactly the fields"):
        core(cli_version=PLACEHOLDER_VERSION)


def test_declaring_a_placeholder_that_is_not_there_is_refused() -> None:
    with pytest.raises(PydanticValidationError, match="must name exactly the fields"):
        core(placeholder_release=True, placeholder_fields=["cli_version"])


def test_a_declared_placeholder_release_is_accepted() -> None:
    document = core(
        placeholder_release=True,
        placeholder_fields=["cli_version"],
        cli_version=PLACEHOLDER_VERSION,
    )
    assert document.placeholder_fields == ["cli_version"]


def test_the_release_flag_must_follow_the_field_list() -> None:
    with pytest.raises(PydanticValidationError, match="placeholder_release must be"):
        core(
            placeholder_release=False,
            placeholder_fields=["cli_version"],
            cli_version=PLACEHOLDER_VERSION,
        )


def test_a_release_with_no_blanks_cannot_be_marked_provisional() -> None:
    with pytest.raises(PydanticValidationError, match="placeholder_release must be"):
        core(placeholder_release=True)


def test_placeholder_fields_must_be_sorted_and_unique() -> None:
    with pytest.raises(PydanticValidationError, match="sorted"):
        core(
            placeholder_release=True,
            placeholder_fields=["cli_version", "cli_source_commit"],
            cli_version=PLACEHOLDER_VERSION,
            cli_source_commit=PLACEHOLDER_COMMIT,
        )


def test_a_field_with_no_placeholder_spelling_cannot_be_declared() -> None:
    with pytest.raises(PydanticValidationError, match="no placeholder spelling"):
        core(placeholder_release=True, placeholder_fields=["engine_digest"])


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("engine_digest", PLACEHOLDER_DIGEST),
        ("catalog_digest", PLACEHOLDER_DIGEST),
        ("protocol_version", PLACEHOLDER_VERSION),
        ("subject_hermes_version", PLACEHOLDER_VERSION),
    ],
)
def test_a_coordinate_read_from_the_tree_can_never_be_blank(
    field: str, value: str
) -> None:
    with pytest.raises(PydanticValidationError, match="can never be placeholders"):
        core(**{field: value})


def test_every_placeholder_kind_has_exactly_one_spelling() -> None:
    document = core(
        placeholder_release=True,
        placeholder_fields=[
            "cli_source_commit",
            "cli_version",
            "release_id",
            "starter_skill_digest",
        ],
        cli_source_commit=PLACEHOLDER_COMMIT,
        cli_version=PLACEHOLDER_VERSION,
        release_id=PLACEHOLDER_VERSION,
        starter_skill_digest=PLACEHOLDER_DIGEST,
    )
    assert declared_placeholder_fields(document.model_dump(mode="json")) == [
        "cli_source_commit",
        "cli_version",
        "release_id",
        "starter_skill_digest",
    ]


def test_an_abbreviated_commit_is_not_a_commit() -> None:
    with pytest.raises(PydanticValidationError):
        core(cli_source_commit="c" * 12)


def test_an_unknown_field_is_refused() -> None:
    with pytest.raises(PydanticValidationError):
        ReleaseCore.model_validate(
            {**bound_fields(), "website_origin": "https://techtree.sh"}
        )


# ---------------------------------------------------------------------------
# Stored bytes
# ---------------------------------------------------------------------------


def test_stored_bytes_round_trip_exactly() -> None:
    raw = render_release_core(core())
    assert render_release_core(parse_release_core(raw)) == raw


def test_stored_bytes_are_sorted_indented_and_newline_terminated() -> None:
    raw = render_release_core(core())
    text = raw.decode("utf-8")
    assert text.endswith("}\n")
    assert '\n  "catalog_digest"' in text
    assert text.index('"catalog_digest"') < text.index('"cli_version"')


def test_a_reindented_document_is_not_the_published_spelling() -> None:
    raw = render_release_core(core())
    assert is_canonical_document(raw)
    assert not is_canonical_document(raw.replace(b"\n  ", b"\n    "))


def test_the_digest_is_taken_over_the_file_bytes() -> None:
    raw = render_release_core(core())
    assert document_digest(raw) != document_digest(raw + b"\n")


def test_a_document_that_is_not_a_release_core_is_a_typed_failure() -> None:
    with pytest.raises(ValidationError, match="not a valid ReleaseCore"):
        parse_release_core(b'{"schema_version": "techtree.release-core.v1"}')


def test_render_document_refuses_nothing_it_can_spell() -> None:
    assert render_document({"b": 1, "a": [True, None]}) == (
        b'{\n  "a": [\n    true,\n    null\n  ],\n  "b": 1\n}\n'
    )


# ---------------------------------------------------------------------------
# Founder-owned inputs
# ---------------------------------------------------------------------------


def founder_inputs() -> dict[str, Any]:
    """Return one complete set of founder-owned release decisions."""
    return {
        "schema_version": "techtree.release-inputs.v1",
        "release_id": "climb-v0.1.0",
        "cli_version": "0.1.0",
        "cli_source_commit": REAL_COMMIT,
        "intro_climb_reference": "hello-world-climb@1",
        "starter_skill_digest": REAL_DIGEST,
        "skill_improver_digest": REAL_DIGEST,
        "minimum_host_hermes_version": "0.19.0",
        "maximum_tested_host_hermes_version": "0.19.3",
    }


def test_release_inputs_accept_only_founder_decisions() -> None:
    assert ReleaseInputs.model_validate(founder_inputs()).cli_version == "0.1.0"


def test_release_inputs_reject_a_derived_coordinate() -> None:
    with pytest.raises(PydanticValidationError):
        ReleaseInputs.model_validate({**founder_inputs(), "engine_digest": REAL_DIGEST})
