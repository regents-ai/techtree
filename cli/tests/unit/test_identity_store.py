"""The local executor identity. Spec section 7.5.

Two things are under test and they are different in kind.

The mechanics: a key is created once, owner-readable only, and the two halves
describe each other. Those are the properties a receipt's signature rests on,
and each one is checked against the files rather than against the object the
store returned.

The prohibitions: the private half never appears in anything that leaves the
identities directory — not in the public identity file, not in an error's
details, not in a proof bundle. Those are checked by looking for it, because a
leak that nobody looks for is a leak nobody finds.
"""

from __future__ import annotations

import stat
from datetime import UTC, datetime
from pathlib import Path

import pytest

from techtree.canonical import digest_object
from techtree.crypto import (
    generate_private_key,
    private_key_bytes,
    public_key_bytes,
    public_key_to_base64,
)
from techtree.errors import ConflictError, NotFoundError, TechtreeError, ValidationError
from techtree.identity.models import LOCAL_IDENTITY_INVALID, ExecutorIdentity
from techtree.identity.service import IdentityService, verify_signed_object
from techtree.identity.store import (
    PRIVATE_KEY_FILENAME,
    PUBLIC_IDENTITY_FILENAME,
    IdentityStore,
)
from techtree.models.base import ArtifactRef, ObjectEnvelope
from techtree.paths import TechtreePaths, paths_from_root

FIXED_TIME = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
def paths(tmp_path: Path) -> TechtreePaths:
    return paths_from_root(tmp_path / "techtree")


@pytest.fixture
def store(paths: TechtreePaths) -> IdentityStore:
    return IdentityStore(paths, clock=lambda: FIXED_TIME)


def artifact() -> ArtifactRef:
    """Return a small protocol object to sign."""
    return ArtifactRef(
        digest=digest_object({"payload": "signed"}),
        media_type="application/json",
        size=17,
        relative_path=None,
    )


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------


def test_a_fresh_machine_has_no_identity(store: IdentityStore) -> None:
    assert store.exists() is False


def test_creation_writes_both_halves_and_returns_the_public_one(
    store: IdentityStore,
) -> None:
    identity = store.create()

    assert store.exists() is True
    assert store.private_key_path.name == PRIVATE_KEY_FILENAME
    assert store.public_identity_path.name == PUBLIC_IDENTITY_FILENAME
    assert identity.kind == "local_ed25519"
    assert identity.algorithm == "ed25519"
    assert identity.created_at == FIXED_TIME


def test_the_private_key_file_is_owner_only(store: IdentityStore) -> None:
    store.create()

    assert stat.S_IMODE(store.private_key_path.stat().st_mode) == 0o600


def test_the_public_identity_file_is_owner_only(store: IdentityStore) -> None:
    store.create()

    assert stat.S_IMODE(store.public_identity_path.stat().st_mode) == 0o600


def test_the_identities_directory_is_owner_traversal_only(
    store: IdentityStore,
) -> None:
    store.create()

    assert stat.S_IMODE(store.directory.stat().st_mode) == 0o700


def test_creating_a_second_identity_is_refused(store: IdentityStore) -> None:
    store.create()

    with pytest.raises(ConflictError) as raised:
        store.create()

    assert raised.value.code == LOCAL_IDENTITY_INVALID


def test_two_machines_create_different_identities(tmp_path: Path) -> None:
    first = IdentityStore(paths_from_root(tmp_path / "one")).create()
    second = IdentityStore(paths_from_root(tmp_path / "two")).create()

    assert first.key_id != second.key_id
    assert first.public_key != second.public_key


def test_the_key_identifier_is_derived_from_the_public_key(
    store: IdentityStore,
) -> None:
    """Derived rather than assigned: two keys cannot share an identifier."""
    identity = store.create()
    private_key = store.load_private()

    from techtree.canonical import sha256_digest_bytes

    assert identity.key_id == sha256_digest_bytes(public_key_bytes(private_key))
    assert identity.public_key == public_key_to_base64(private_key.public_key())


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def test_loading_from_a_machine_with_no_identity_says_so(
    store: IdentityStore,
) -> None:
    with pytest.raises(NotFoundError) as public:
        store.load_public()
    with pytest.raises(NotFoundError) as private:
        store.load_private()

    assert public.value.code == LOCAL_IDENTITY_INVALID
    assert private.value.code == LOCAL_IDENTITY_INVALID


def test_a_truncated_private_key_is_refused(store: IdentityStore) -> None:
    store.create()
    store.private_key_path.write_bytes(b"\x01" * 16)

    with pytest.raises(ValidationError) as raised:
        store.load_private()

    assert raised.value.code == LOCAL_IDENTITY_INVALID


def test_a_corrupt_public_identity_is_refused(store: IdentityStore) -> None:
    store.create()
    store.public_identity_path.write_text("{}", encoding="utf-8")

    with pytest.raises(ValidationError) as raised:
        store.load_public()

    assert raised.value.code == LOCAL_IDENTITY_INVALID


def test_the_pair_verifies_itself(store: IdentityStore) -> None:
    store.create()

    assert store.verify_pair() is True


def test_a_mismatched_pair_does_not_verify(store: IdentityStore) -> None:
    """A public half that describes some other key is not merely wrong data."""
    store.create()
    stranger = generate_private_key()
    replacement = ExecutorIdentity(
        kind="local_ed25519",
        key_id=store.load_public().key_id,
        algorithm="ed25519",
        public_key=public_key_to_base64(stranger.public_key()),
        created_at=FIXED_TIME,
    )
    store.public_identity_path.write_bytes(
        replacement.model_dump_json().encode("utf-8")
    )

    assert store.verify_pair() is False


# ---------------------------------------------------------------------------
# Signing
# ---------------------------------------------------------------------------


def test_ensure_creates_an_identity_and_then_returns_the_same_one(
    store: IdentityStore,
) -> None:
    service = IdentityService(store)

    first = service.ensure()
    second = service.ensure()

    assert first == second


def test_ensure_refuses_an_identity_whose_halves_disagree(
    store: IdentityStore,
) -> None:
    service = IdentityService(store)
    service.ensure()
    store.private_key_path.write_bytes(private_key_bytes(generate_private_key()))

    with pytest.raises(TechtreeError) as raised:
        service.ensure()

    assert raised.value.code == LOCAL_IDENTITY_INVALID


def test_a_signed_object_round_trips(store: IdentityStore) -> None:
    service = IdentityService(store)
    identity = service.ensure()

    envelope = service.sign_object(artifact())

    assert envelope.signature is not None
    assert envelope.signature.key_id == identity.key_id
    assert envelope.payload_digest == digest_object(artifact())
    assert service.verify_envelope(envelope).verified is True


def test_signing_the_same_object_twice_produces_the_same_bytes(
    store: IdentityStore,
) -> None:
    """Ed25519 is deterministic, so a proof written twice is the same proof."""
    service = IdentityService(store)
    service.ensure()

    first = service.sign_object(artifact())
    second = service.sign_object(artifact())

    assert first == second


def test_an_edited_payload_breaks_verification(store: IdentityStore) -> None:
    service = IdentityService(store)
    identity = service.ensure()
    envelope = service.sign_object(artifact())

    edited = ObjectEnvelope[ArtifactRef](
        payload=envelope.payload.model_copy(update={"size": 18}),
        payload_digest=envelope.payload_digest,
        signature=envelope.signature,
    )
    result = verify_signed_object(identity=identity, envelope=edited)

    assert result.verified is False
    assert [message.id for message in result.failures] == [
        "object.payload_digest",
        "object.signature",
    ]


def test_an_unsigned_envelope_does_not_verify(store: IdentityStore) -> None:
    service = IdentityService(store)
    identity = service.ensure()

    result = verify_signed_object(
        identity=identity,
        envelope=ObjectEnvelope[ArtifactRef](
            payload=artifact(),
            payload_digest=digest_object(artifact()),
            signature=None,
        ),
    )

    assert result.verified is False
    assert [message.id for message in result.failures] == ["object.signature_present"]


def test_another_machines_key_does_not_verify_this_ones_signature(
    tmp_path: Path,
) -> None:
    mine = IdentityService(IdentityStore(paths_from_root(tmp_path / "mine")))
    stranger = IdentityService(IdentityStore(paths_from_root(tmp_path / "stranger")))
    mine.ensure()
    other = stranger.ensure()

    result = verify_signed_object(identity=other, envelope=mine.sign_object(artifact()))

    assert result.verified is False
    assert "object.signature_key" in [message.id for message in result.failures]


# ---------------------------------------------------------------------------
# The private half never leaves
# ---------------------------------------------------------------------------


def test_the_private_key_is_not_in_the_public_identity_file(
    store: IdentityStore,
) -> None:
    store.create()
    secret = private_key_bytes(store.load_private())

    stored = store.public_identity_path.read_bytes()

    assert secret not in stored
    assert public_key_to_base64(store.load_private().public_key()).encode() in stored


def test_the_private_key_is_not_in_a_signed_envelope(store: IdentityStore) -> None:
    service = IdentityService(store)
    service.ensure()
    secret = private_key_bytes(store.load_private())

    from techtree.canonical import canonical_json_bytes

    assert secret not in canonical_json_bytes(service.sign_object(artifact()))


def test_no_error_from_the_store_carries_key_material(store: IdentityStore) -> None:
    store.create()
    secret = private_key_bytes(store.load_private()).hex()
    store.private_key_path.write_bytes(b"\x01" * 8)

    with pytest.raises(ValidationError) as raised:
        store.load_private()

    assert secret not in str(raised.value.details)
    assert secret not in raised.value.message
