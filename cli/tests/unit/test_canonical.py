"""Canonicalization, digests, protocol base models, and the Verifiers boundary.

Spec sections 10.7, 11.2, and 2.8; WP0 acceptance criteria in section 26.

The point of every test here is that two honest parties, working from the same
object, must land on the same bytes and therefore the same digest — and that
anything which could make them disagree is refused rather than guessed at.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Any

import pytest
from pydantic import ValidationError as PydanticValidationError

from techtree.canonical import (
    VERIFIERS_TASK_HASH_LENGTH,
    canonical_json_bytes,
    canonical_json_text,
    digest_object,
    normalize_verifiers_task_hash,
    sha256_digest_bytes,
    to_json_value,
    validate_digest,
    verify_bytes_digest,
    verify_object_digest,
)
from techtree.constants import DIGEST_PREFIX
from techtree.errors import ValidationError
from techtree.models.base import (
    ArtifactRef,
    ObjectEnvelope,
    ProtocolModel,
    PublicKeyRef,
    SignatureEnvelope,
    StateModel,
)

HEX_A = "ab" * 32
HEX_B = "cd" * 32
DIGEST_A = f"{DIGEST_PREFIX}{HEX_A}"
DIGEST_B = f"{DIGEST_PREFIX}{HEX_B}"

# Published SHA-256 vectors, so the digest helper is checked against the
# standard rather than against itself.
SHA256_OF_EMPTY = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
SHA256_OF_ABC = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


class Flavor(StrEnum):
    """A string enum, the only enum kind protocol documents use."""

    BASELINE = "baseline"
    CANDIDATE = "candidate"


class Sample(ProtocolModel):
    """A small protocol object with one field of each interesting kind."""

    name: str
    count: int
    ratio: float
    enabled: bool
    flavor: Flavor
    observed_at: datetime
    tags: list[str]
    extra: dict[str, int]


def make_sample(**overrides: Any) -> Sample:
    """Build the reference sample, optionally changing one field."""
    fields: dict[str, Any] = {
        "name": "procedure-transfer-dev",
        "count": 24,
        "ratio": 0.5,
        "enabled": True,
        "flavor": Flavor.BASELINE,
        "observed_at": datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
        "tags": ["alpha", "beta"],
        "extra": {"b": 2, "a": 1},
    }
    fields.update(overrides)
    return Sample(**fields)


def make_artifact_ref(**overrides: Any) -> ArtifactRef:
    fields: dict[str, Any] = {
        "digest": DIGEST_A,
        "media_type": "application/json",
        "size": 128,
        "relative_path": "public/campaign.json",
    }
    fields.update(overrides)
    return ArtifactRef(**fields)


# ---------------------------------------------------------------------------
# RFC 8785 shape
# ---------------------------------------------------------------------------


def test_object_keys_are_sorted() -> None:
    assert canonical_json_text({"b": 1, "a": 2}) == '{"a":2,"b":1}'


def test_output_has_no_insignificant_whitespace() -> None:
    text = canonical_json_text({"a": [1, 2], "b": {"c": 3}})
    assert text == '{"a":[1,2],"b":{"c":3}}'


def test_output_is_utf8_bytes() -> None:
    assert canonical_json_bytes({"k": "v"}) == b'{"k":"v"}'


def test_array_order_is_preserved() -> None:
    # Arrays are ordered data. Sorting them would destroy meaning, and
    # membership commitments depend on task order.
    assert canonical_json_text(["b", "a"]) == '["b","a"]'
    assert canonical_json_text(["a", "b"]) == '["a","b"]'


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_repeated_serialization_is_byte_identical() -> None:
    sample = make_sample()
    first = canonical_json_bytes(sample)
    for _ in range(16):
        assert canonical_json_bytes(sample) == first


def test_independently_built_equal_objects_agree() -> None:
    assert canonical_json_bytes(make_sample()) == canonical_json_bytes(make_sample())
    assert digest_object(make_sample()) == digest_object(make_sample())


def test_key_insertion_order_does_not_change_the_digest() -> None:
    forward = {"alpha": 1, "beta": 2, "gamma": 3}
    reversed_order = {"gamma": 3, "beta": 2, "alpha": 1}
    assert list(forward) != list(reversed_order)
    assert digest_object(forward) == digest_object(reversed_order)


def test_source_whitespace_does_not_change_the_digest() -> None:
    compact = json.loads('{"a":1,"b":[2,3]}')
    spaced = json.loads('{\n  "b" : [ 2, 3 ],\n  "a" : 1\n}\n')
    assert digest_object(compact) == digest_object(spaced)


def test_nested_key_order_does_not_change_the_digest() -> None:
    forward = {"outer": {"a": 1, "b": {"x": 1, "y": 2}}}
    shuffled = {"outer": {"b": {"y": 2, "x": 1}, "a": 1}}
    assert digest_object(forward) == digest_object(shuffled)


# ---------------------------------------------------------------------------
# Sensitivity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", "procedure-transfer-devv"),
        ("count", 25),
        ("ratio", 0.5000000001),
        ("enabled", False),
        ("flavor", Flavor.CANDIDATE),
        ("observed_at", datetime(2026, 1, 2, 3, 4, 6, tzinfo=UTC)),
        ("tags", ["alpha", "beta", "gamma"]),
        ("tags", ["beta", "alpha"]),
        ("extra", {"a": 1, "b": 3}),
    ],
)
def test_one_field_mutation_changes_the_digest(field: str, value: Any) -> None:
    baseline = digest_object(make_sample())
    mutated = digest_object(make_sample(**{field: value}))
    assert mutated != baseline


def test_microsecond_change_changes_the_digest() -> None:
    without = make_sample(observed_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC))
    with_micros = make_sample(
        observed_at=datetime(2026, 1, 2, 3, 4, 5, 1, tzinfo=UTC),
    )
    assert digest_object(without) != digest_object(with_micros)


def test_true_and_one_are_different_values() -> None:
    assert canonical_json_text({"a": True}) == '{"a":true}'
    assert canonical_json_text({"a": 1}) == '{"a":1}'
    assert digest_object({"a": True}) != digest_object({"a": 1})


def test_absent_and_null_are_the_same_for_optional_fields() -> None:
    # Optional fields are always emitted, so omitting one at construction time
    # and passing ``None`` produce identical bytes.
    omitted = ArtifactRef(digest=DIGEST_A, media_type="application/json", size=1)
    explicit = ArtifactRef(
        digest=DIGEST_A,
        media_type="application/json",
        size=1,
        relative_path=None,
    )
    assert canonical_json_bytes(omitted) == canonical_json_bytes(explicit)
    assert b'"relative_path":null' in canonical_json_bytes(omitted)


# ---------------------------------------------------------------------------
# Datetimes
# ---------------------------------------------------------------------------


def test_utc_datetime_is_spelled_with_z() -> None:
    moment = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    assert canonical_json_text(moment) == '"2026-01-02T03:04:05Z"'


def test_offset_datetimes_are_converted_to_utc() -> None:
    in_utc = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    same_instant = datetime(
        2026, 1, 2, 8, 34, 5, tzinfo=timezone(timedelta(hours=5, minutes=30))
    )
    assert in_utc == same_instant
    assert canonical_json_bytes(in_utc) == canonical_json_bytes(same_instant)
    assert canonical_json_text(same_instant) == '"2026-01-02T03:04:05Z"'


def test_microseconds_survive_canonicalization() -> None:
    moment = datetime(2026, 1, 2, 3, 4, 5, 123456, tzinfo=UTC)
    assert canonical_json_text(moment) == '"2026-01-02T03:04:05.123456Z"'


@pytest.mark.parametrize(
    "moment",
    [
        datetime(2026, 1, 2, 3, 4, 5),
        datetime(1970, 1, 1),
        datetime(2026, 6, 1, 12, 0, 0, 500),
    ],
)
def test_naive_datetimes_fail(moment: datetime) -> None:
    with pytest.raises(ValidationError, match="naive datetime"):
        canonical_json_bytes(moment)


def test_naive_datetime_nested_in_a_mapping_fails() -> None:
    with pytest.raises(ValidationError, match="naive datetime"):
        canonical_json_bytes({"observed_at": datetime(2026, 1, 1)})


# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
        math.nan,
        math.inf,
    ],
)
def test_non_finite_floats_fail(value: float) -> None:
    with pytest.raises(ValidationError, match="non-finite"):
        canonical_json_bytes(value)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_floats_fail_inside_containers(value: float) -> None:
    with pytest.raises(ValidationError, match="non-finite"):
        canonical_json_bytes({"score": [value]})


@pytest.mark.parametrize("text", ["NaN", "Infinity", "-Infinity", "sNaN"])
def test_non_finite_decimals_fail(text: str) -> None:
    with pytest.raises(ValidationError, match="non-finite decimal"):
        canonical_json_bytes(Decimal(text))


def test_finite_decimals_become_numbers() -> None:
    assert canonical_json_text(Decimal("2.50")) == "2.5"
    assert canonical_json_text(Decimal("3")) == "3"


def test_integers_beyond_the_json_safe_range_fail() -> None:
    # RFC 8785 numbers are IEEE 754 doubles; beyond 2**53 two different
    # integers would serialize to the same text.
    with pytest.raises(ValidationError, match="cannot be canonicalized"):
        canonical_json_bytes(2**53)


def test_integers_inside_the_safe_range_are_kept_exact() -> None:
    assert canonical_json_text(2**53 - 1) == "9007199254740991"
    assert canonical_json_text(-(2**53) + 1) == "-9007199254740991"


# ---------------------------------------------------------------------------
# Supported and unsupported types
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("text", "text"),
        (7, 7),
        (7.5, 7.5),
        (True, True),
        (False, False),
        (Flavor.CANDIDATE, "candidate"),
        (Decimal("1.25"), 1.25),
        (Path("a/b/c.json"), "a/b/c.json"),
        (PurePosixPath("x/y"), "x/y"),
        (["a", 1], ["a", 1]),
        (("a", 1), ["a", 1]),
        ({"k": "v"}, {"k": "v"}),
    ],
)
def test_to_json_value_conversions(value: object, expected: object) -> None:
    assert to_json_value(value) == expected


def test_nested_models_are_converted_recursively() -> None:
    envelope = ObjectEnvelope[ArtifactRef](
        payload=make_artifact_ref(),
        payload_digest=DIGEST_B,
    )
    converted = to_json_value(envelope)
    assert converted == {
        "payload": {
            "digest": DIGEST_A,
            "media_type": "application/json",
            "relative_path": "public/campaign.json",
            "size": 128,
        },
        "payload_digest": DIGEST_B,
        "signature": None,
    }


@pytest.mark.parametrize(
    ("value", "match"),
    [
        (b"bytes", "base64"),
        (bytearray(b"bytes"), "base64"),
        ({"a", "b"}, "no defined order"),
        (frozenset({"a"}), "no defined order"),
        (object(), "no canonical JSON representation"),
        (complex(1, 2), "no canonical JSON representation"),
        (Exception("boom"), "no canonical JSON representation"),
    ],
)
def test_unsupported_types_fail(value: object, match: str) -> None:
    with pytest.raises(ValidationError, match=match):
        canonical_json_bytes(value)


def test_non_string_mapping_keys_fail() -> None:
    with pytest.raises(ValidationError, match="mapping keys must be strings"):
        canonical_json_bytes({1: "one"})


# ---------------------------------------------------------------------------
# Digests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("data", "expected_hex"),
    [
        (b"", SHA256_OF_EMPTY),
        (b"abc", SHA256_OF_ABC),
    ],
)
def test_sha256_digest_bytes_matches_published_vectors(
    data: bytes, expected_hex: str
) -> None:
    assert sha256_digest_bytes(data) == f"{DIGEST_PREFIX}{expected_hex}"


def test_digest_object_is_the_digest_of_the_canonical_bytes() -> None:
    sample = make_sample()
    expected = hashlib.sha256(canonical_json_bytes(sample)).hexdigest()
    assert digest_object(sample) == f"{DIGEST_PREFIX}{expected}"


def test_digests_are_lowercase_and_prefixed() -> None:
    digest = digest_object(make_sample())
    assert digest.startswith(DIGEST_PREFIX)
    body = digest.removeprefix(DIGEST_PREFIX)
    assert len(body) == 64
    assert body == body.lower()


def test_verify_bytes_digest_round_trip() -> None:
    assert verify_bytes_digest(b"abc", sha256_digest_bytes(b"abc"))
    assert not verify_bytes_digest(b"abd", sha256_digest_bytes(b"abc"))


def test_verify_object_digest_round_trip() -> None:
    sample = make_sample()
    assert verify_object_digest(sample, digest_object(sample))
    assert not verify_object_digest(make_sample(count=25), digest_object(sample))


@pytest.mark.parametrize(
    "expected",
    [
        HEX_A,
        f"{DIGEST_PREFIX}{HEX_A.upper()}",
        f"{DIGEST_PREFIX}{HEX_A[:-1]}",
        f"sha512:{HEX_A}",
        "",
    ],
)
def test_verification_rejects_a_malformed_expected_digest(expected: str) -> None:
    # A digest that is not a digest is a broken caller, not a mismatch.
    with pytest.raises(ValidationError, match="digest must be"):
        verify_bytes_digest(b"abc", expected)


@pytest.mark.parametrize("value", [DIGEST_A, DIGEST_B, f"{DIGEST_PREFIX}{'0' * 64}"])
def test_validate_digest_accepts_well_formed_digests(value: str) -> None:
    assert validate_digest(value) == value


@pytest.mark.parametrize(
    "value",
    [
        HEX_A,
        f"{DIGEST_PREFIX}{HEX_A.upper()}",
        f"{DIGEST_PREFIX}{HEX_A}extra",
        f"{DIGEST_PREFIX}{HEX_A[:63]}",
        f" {DIGEST_PREFIX}{HEX_A}",
        f"{DIGEST_PREFIX}{HEX_A} ",
        f"{DIGEST_PREFIX}{'g' * 64}",
        "sha256:",
        "",
    ],
)
def test_validate_digest_rejects_everything_else(value: str) -> None:
    with pytest.raises(ValidationError, match="digest must be"):
        validate_digest(value)


# ---------------------------------------------------------------------------
# Verifiers task-hash boundary, spec section 2.8
# ---------------------------------------------------------------------------


def test_raw_task_hash_normalizes() -> None:
    assert normalize_verifiers_task_hash(HEX_A) == DIGEST_A


def test_task_hash_length_constant_is_sixty_four() -> None:
    assert VERIFIERS_TASK_HASH_LENGTH == 64


def test_already_prefixed_input_is_rejected() -> None:
    # The boundary function is the only door raw Verifiers data comes through.
    # Accepting a prefixed value here would let an unchecked string enter the
    # protocol already looking like a digest.
    with pytest.raises(ValidationError, match="unprefixed"):
        normalize_verifiers_task_hash(DIGEST_A)


def test_uppercase_task_hash_is_rejected() -> None:
    with pytest.raises(ValidationError, match="lowercase hexadecimal"):
        normalize_verifiers_task_hash(HEX_A.upper())


def test_mixed_case_task_hash_is_rejected() -> None:
    mixed = HEX_A[:-1] + "B"
    with pytest.raises(ValidationError, match="lowercase hexadecimal"):
        normalize_verifiers_task_hash(mixed)


@pytest.mark.parametrize(
    "raw",
    ["", "ab", HEX_A[:63], HEX_A + "a", HEX_A * 2],
)
def test_wrong_length_task_hash_is_rejected(raw: str) -> None:
    with pytest.raises(ValidationError, match="exactly 64 characters"):
        normalize_verifiers_task_hash(raw)


@pytest.mark.parametrize(
    "raw",
    [
        "g" * 64,
        "z" + "a" * 63,
        "a" * 63 + "!",
        "a" * 63 + " ",
        " " + "a" * 63,
        "a" * 32 + "-" + "a" * 31,
        "a" * 63 + "\n",
    ],
)
def test_invalid_character_task_hash_is_rejected(raw: str) -> None:
    assert len(raw) == VERIFIERS_TASK_HASH_LENGTH
    with pytest.raises(ValidationError, match="lowercase hexadecimal"):
        normalize_verifiers_task_hash(raw)


def test_normalized_task_hashes_pass_digest_validation() -> None:
    assert validate_digest(normalize_verifiers_task_hash(HEX_A)) == DIGEST_A


def test_membership_comparison_is_stable_across_round_trips() -> None:
    # A membership commitment is compared by normalizing both sides; the
    # comparison has to survive being taken twice.
    raw_hashes = [f"{index:064x}" for index in range(8)]
    first = [normalize_verifiers_task_hash(value) for value in raw_hashes]
    second = [normalize_verifiers_task_hash(value) for value in raw_hashes]
    assert first == second
    assert digest_object(first) == digest_object(second)
    assert set(first) == set(second)


def test_membership_comparison_detects_a_single_changed_task() -> None:
    raw_hashes = [f"{index:064x}" for index in range(8)]
    changed = [*raw_hashes[:-1], f"{99:064x}"]
    first = [normalize_verifiers_task_hash(value) for value in raw_hashes]
    second = [normalize_verifiers_task_hash(value) for value in changed]
    assert digest_object(first) != digest_object(second)


# ---------------------------------------------------------------------------
# Protocol base models, spec section 11.2
# ---------------------------------------------------------------------------


def test_protocol_models_reject_unknown_fields() -> None:
    with pytest.raises(PydanticValidationError, match="Extra inputs"):
        ArtifactRef(
            digest=DIGEST_A,
            media_type="application/json",
            size=1,
            surprise="no",  # type: ignore[call-arg]
        )


def test_protocol_models_are_frozen() -> None:
    reference = make_artifact_ref()
    with pytest.raises(PydanticValidationError, match="frozen"):
        reference.size = 2


def test_state_models_are_mutable_but_still_validate() -> None:
    class LocalState(StateModel):
        label: str

    state = LocalState(label="a")
    state.label = "b"
    assert state.label == "b"
    with pytest.raises(PydanticValidationError):
        state.label = 3  # type: ignore[assignment]
    with pytest.raises(PydanticValidationError, match="Extra inputs"):
        LocalState(label="a", other=1)  # type: ignore[call-arg]


@pytest.mark.parametrize(
    "digest",
    [HEX_A, f"{DIGEST_PREFIX}{HEX_A.upper()}", f"{DIGEST_PREFIX}{'z' * 64}", ""],
)
def test_digest_fields_enforce_the_digest_syntax(digest: str) -> None:
    with pytest.raises(PydanticValidationError):
        ArtifactRef(digest=digest, media_type="application/json", size=1)


@pytest.mark.parametrize("size", [0, -1, -1000])
def test_artifact_size_must_be_positive(size: int) -> None:
    with pytest.raises(PydanticValidationError, match="greater than 0"):
        ArtifactRef(digest=DIGEST_A, media_type="application/json", size=size)


@pytest.mark.parametrize("key_id", ["", " ", "\t\n"])
def test_key_ids_must_not_be_blank(key_id: str) -> None:
    with pytest.raises(PydanticValidationError):
        SignatureEnvelope(algorithm="ed25519", key_id=key_id, signature="AAAA")


@pytest.mark.parametrize("value", ["not base64!", "AAA", "====", "AA=A"])
def test_signature_and_key_material_must_be_base64(value: str) -> None:
    with pytest.raises(PydanticValidationError, match="base64"):
        SignatureEnvelope(algorithm="ed25519", key_id="dev", signature=value)
    with pytest.raises(PydanticValidationError, match="base64"):
        PublicKeyRef(algorithm="ed25519", key_id="dev", public_key=value)


def test_only_ed25519_is_accepted() -> None:
    with pytest.raises(PydanticValidationError):
        SignatureEnvelope(
            algorithm="rsa",  # type: ignore[arg-type]
            key_id="dev",
            signature="AAAA",
        )


def test_utc_aware_datetimes_are_normalized_by_the_model() -> None:
    class Timed(ProtocolModel):
        at: datetime

    east = timezone(timedelta(hours=9))
    assert Timed(at=datetime(2026, 1, 2, 12, tzinfo=east)).at == datetime(
        2026, 1, 2, 3, tzinfo=UTC
    )


def test_object_envelope_does_not_recompute_its_payload_digest() -> None:
    # Recomputing on construction would make the field incapable of reporting
    # the mismatch it exists to report.
    payload = make_artifact_ref()
    envelope = ObjectEnvelope[ArtifactRef](
        payload=payload,
        payload_digest=DIGEST_B,
    )
    assert envelope.payload_digest == DIGEST_B
    assert not verify_object_digest(envelope.payload, envelope.payload_digest)

    honest = ObjectEnvelope[ArtifactRef](
        payload=payload,
        payload_digest=digest_object(payload),
    )
    assert verify_object_digest(honest.payload, honest.payload_digest)


def test_protocol_documents_load_from_json_bytes() -> None:
    original = make_sample()
    reloaded = Sample.model_validate_json(original.model_dump_json())
    assert canonical_json_bytes(reloaded) == canonical_json_bytes(original)
    assert digest_object(reloaded) == digest_object(original)
