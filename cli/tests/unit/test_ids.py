"""Prefixed local identifiers. Spec section 10.6.

Identifiers name things locally; digests say what things are. These tests pin
the syntax tightly so that a malformed or foreign identifier is rejected where
it is written, and they check the one property that keeps the two concepts
apart: an identifier carries no information about content.
"""

from __future__ import annotations

import re

import pytest

from techtree.canonical import digest_object
from techtree.errors import ValidationError
from techtree.ids import ID_PREFIXES, id_prefix, new_id, validate_id

ID_SHAPE = re.compile(r"^[a-z]+_[0-9a-f]{32}$")

#: The exact set spec section 10.6 lists. Written out rather than derived so a
#: change to the module cannot silently change the contract.
EXPECTED_PREFIXES = frozenset(
    {"campaign", "climb", "draft", "run", "receipt", "uplift", "policy"}
)

BODY = "0123456789abcdef" * 2


def test_prefix_set_matches_the_specification() -> None:
    assert ID_PREFIXES == EXPECTED_PREFIXES


# ---------------------------------------------------------------------------
# new_id
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("prefix", sorted(EXPECTED_PREFIXES))
def test_new_id_has_the_documented_shape(prefix: str) -> None:
    value = new_id(prefix)
    assert ID_SHAPE.fullmatch(value), value
    assert value.startswith(f"{prefix}_")
    assert len(value) == len(prefix) + 1 + 32


@pytest.mark.parametrize("prefix", sorted(EXPECTED_PREFIXES))
def test_new_id_round_trips_through_validation(prefix: str) -> None:
    value = new_id(prefix)
    assert validate_id(value) == value
    assert validate_id(value, prefix) == value
    assert id_prefix(value) == prefix


def test_new_ids_are_distinct() -> None:
    values = {new_id("run") for _ in range(256)}
    assert len(values) == 256


def test_new_id_body_is_lowercase_hexadecimal() -> None:
    body = new_id("draft").removeprefix("draft_")
    assert body == body.lower()
    assert set(body) <= set("0123456789abcdef")


@pytest.mark.parametrize(
    "prefix",
    ["", "RUN", "Run", "engine", "task", "run_", "run ", "sha256", "identity"],
)
def test_new_id_rejects_unknown_prefixes(prefix: str) -> None:
    with pytest.raises(ValidationError, match="unknown identifier prefix"):
        new_id(prefix)


# ---------------------------------------------------------------------------
# validate_id
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("prefix", sorted(EXPECTED_PREFIXES))
def test_validate_id_accepts_a_well_formed_identifier(prefix: str) -> None:
    value = f"{prefix}_{BODY}"
    assert validate_id(value) == value


@pytest.mark.parametrize(
    ("value", "reason"),
    [
        ("", "empty"),
        ("run", "no separator"),
        ("run_", "no body"),
        (BODY, "no prefix"),
        (f"_{BODY}", "empty prefix"),
        (f"run_{BODY[:31]}", "body too short"),
        (f"run_{BODY}0", "body too long"),
        (f"run_{BODY.upper()}", "uppercase body"),
        (f"RUN_{BODY}", "uppercase prefix"),
        (f"Run_{BODY}", "mixed-case prefix"),
        (f"run_{'g' * 32}", "non-hexadecimal body"),
        (f"run_{BODY[:31]}-", "hyphen in body"),
        (f"run-{BODY}", "hyphen separator"),
        (f"run__{BODY}", "double separator"),
        (f" run_{BODY}", "leading space"),
        (f"run_{BODY} ", "trailing space"),
        (f"run_{BODY}\n", "trailing newline"),
        (f"run_{BODY}_extra", "trailing segment"),
        (f"sha256:{BODY}", "digest shape"),
        (f"engine_{BODY}", "unknown prefix"),
        (f"1run_{BODY}", "prefix starts with a digit"),
    ],
)
def test_validate_id_rejects_malformed_identifiers(value: str, reason: str) -> None:
    assert reason
    with pytest.raises(ValidationError):
        validate_id(value)


def test_validate_id_enforces_an_expected_prefix() -> None:
    value = f"run_{BODY}"
    assert validate_id(value, "run") == value
    with pytest.raises(ValidationError, match="expected a draft identifier"):
        validate_id(value, "draft")


def test_validate_id_rejects_an_unknown_expected_prefix() -> None:
    with pytest.raises(ValidationError, match="unknown identifier prefix"):
        validate_id(f"run_{BODY}", "engine")


def test_validation_errors_carry_machine_readable_details() -> None:
    with pytest.raises(ValidationError) as caught:
        validate_id("nonsense")
    assert caught.value.details["value"] == "nonsense"
    assert caught.value.code == "validation_error"


# ---------------------------------------------------------------------------
# id_prefix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("prefix", sorted(EXPECTED_PREFIXES))
def test_id_prefix_returns_the_namespace(prefix: str) -> None:
    assert id_prefix(f"{prefix}_{BODY}") == prefix


@pytest.mark.parametrize("value", ["", "run", f"RUN_{BODY}", f"engine_{BODY}"])
def test_id_prefix_rejects_invalid_identifiers(value: str) -> None:
    with pytest.raises(ValidationError):
        id_prefix(value)


# ---------------------------------------------------------------------------
# Identifiers are not integrity values
# ---------------------------------------------------------------------------


def test_identical_content_gets_different_identifiers() -> None:
    # Two drafts of the same thing are two drafts. Sameness of content is a
    # question only a digest answers.
    content = {"climb": "hello-world-climb", "version": 1}
    assert digest_object(content) == digest_object(dict(content))
    assert new_id("draft") != new_id("draft")
