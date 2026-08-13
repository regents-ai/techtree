"""Ed25519 primitives and the WP0–WP5 prohibitions around them.

Spec sections 10.8, 2.6, and 2.7; decisions document 0001.

Two things are under test. First, that the primitives are correct: a signature
made over a digest verifies with the matching public key and fails every other
way it could be presented. Second — and just as binding — that nothing in the
package actually uses them yet. WP0 freezes the shape of signing; it does not
turn signing on, does not create device keys, and does not store identities.
"""

from __future__ import annotations

import ast
import base64
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from pydantic import ValidationError as PydanticValidationError

from techtree.canonical import digest_object, sha256_digest_bytes
from techtree.constants import DIGEST_PREFIX
from techtree.crypto import (
    ED25519_PRIVATE_KEY_BYTES,
    ED25519_PUBLIC_KEY_BYTES,
    ED25519_SIGNATURE_BYTES,
    generate_private_key,
    load_private_key,
    load_public_key,
    private_key_bytes,
    public_key_bytes,
    public_key_to_base64,
    sign_digest,
    verify_signature,
)
from techtree.errors import ValidationError
from techtree.models.base import SignatureEnvelope

DIGEST = sha256_digest_bytes(b"techtree")
OTHER_DIGEST = sha256_digest_bytes(b"techtree ")
KEY_ID = "dev-key-1"

PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "src" / "techtree"


@pytest.fixture
def private_key() -> Ed25519PrivateKey:
    return generate_private_key()


@pytest.fixture
def public_key(private_key: Ed25519PrivateKey) -> Ed25519PublicKey:
    return private_key.public_key()


@pytest.fixture
def signature(private_key: Ed25519PrivateKey) -> SignatureEnvelope:
    return sign_digest(private_key, DIGEST, key_id=KEY_ID)


def corrupt(envelope: SignatureEnvelope, *, index: int = 0) -> SignatureEnvelope:
    """Return the same signature with one byte flipped."""
    raw = bytearray(base64.b64decode(envelope.signature))
    raw[index] ^= 0x01
    return SignatureEnvelope(
        algorithm=envelope.algorithm,
        key_id=envelope.key_id,
        signature=base64.b64encode(bytes(raw)).decode("ascii"),
    )


# ---------------------------------------------------------------------------
# Key material
# ---------------------------------------------------------------------------


def test_generate_private_key_returns_a_fresh_key() -> None:
    first = generate_private_key()
    second = generate_private_key()
    assert private_key_bytes(first) != private_key_bytes(second)


def test_raw_key_sizes(private_key: Ed25519PrivateKey) -> None:
    assert ED25519_PRIVATE_KEY_BYTES == 32
    assert ED25519_PUBLIC_KEY_BYTES == 32
    assert ED25519_SIGNATURE_BYTES == 64
    assert len(private_key_bytes(private_key)) == ED25519_PRIVATE_KEY_BYTES
    assert len(public_key_bytes(private_key)) == ED25519_PUBLIC_KEY_BYTES


def test_private_key_round_trips_through_raw_bytes(
    private_key: Ed25519PrivateKey,
) -> None:
    restored = load_private_key(private_key_bytes(private_key))
    assert private_key_bytes(restored) == private_key_bytes(private_key)
    assert public_key_bytes(restored) == public_key_bytes(private_key)


def test_public_key_round_trips_through_raw_bytes(
    private_key: Ed25519PrivateKey,
) -> None:
    restored = load_public_key(public_key_bytes(private_key))
    assert restored.public_bytes_raw() == public_key_bytes(private_key)


def test_a_restored_key_verifies_its_own_signatures(
    private_key: Ed25519PrivateKey,
) -> None:
    envelope = sign_digest(private_key, DIGEST, key_id=KEY_ID)
    restored = load_public_key(public_key_bytes(private_key))
    assert verify_signature(restored, DIGEST, envelope)


@pytest.mark.parametrize("length", [0, 1, 31, 33, 64])
def test_private_keys_of_the_wrong_length_fail(length: int) -> None:
    with pytest.raises(ValidationError, match="32 raw bytes"):
        load_private_key(b"\x01" * length)


@pytest.mark.parametrize("length", [0, 1, 31, 33, 64])
def test_public_keys_of_the_wrong_length_fail(length: int) -> None:
    with pytest.raises(ValidationError, match="32 raw bytes"):
        load_public_key(b"\x01" * length)


def test_public_key_to_base64_is_decodable(private_key: Ed25519PrivateKey) -> None:
    encoded = public_key_to_base64(private_key.public_key())
    assert base64.b64decode(encoded, validate=True) == public_key_bytes(private_key)


# ---------------------------------------------------------------------------
# Signing and verification
# ---------------------------------------------------------------------------


def test_signature_envelope_shape(signature: SignatureEnvelope) -> None:
    assert signature.algorithm == "ed25519"
    assert signature.key_id == KEY_ID
    raw = base64.b64decode(signature.signature, validate=True)
    assert len(raw) == ED25519_SIGNATURE_BYTES


def test_sign_and_verify_round_trip(
    public_key: Ed25519PublicKey, signature: SignatureEnvelope
) -> None:
    assert verify_signature(public_key, DIGEST, signature)


def test_signing_is_deterministic(private_key: Ed25519PrivateKey) -> None:
    # Ed25519 signatures are deterministic, so an attested digest has exactly
    # one signature per key and two signers cannot be told apart by noise.
    first = sign_digest(private_key, DIGEST, key_id=KEY_ID)
    second = sign_digest(private_key, DIGEST, key_id=KEY_ID)
    assert first.signature == second.signature


def test_the_signed_message_is_the_ascii_digest_string(
    private_key: Ed25519PrivateKey, public_key: Ed25519PublicKey
) -> None:
    envelope = sign_digest(private_key, DIGEST, key_id=KEY_ID)
    raw = base64.b64decode(envelope.signature)
    # Verifying directly against the digest text proves the envelope does not
    # quietly sign something else, such as the canonical bytes.
    public_key.verify(raw, DIGEST.encode("ascii"))


def test_a_real_object_digest_round_trips(private_key: Ed25519PrivateKey) -> None:
    from techtree.models.base import ArtifactRef

    artifact = ArtifactRef(
        digest=sha256_digest_bytes(b"payload"),
        media_type="application/json",
        size=7,
    )
    digest = digest_object(artifact)
    envelope = sign_digest(private_key, digest, key_id=KEY_ID)
    assert verify_signature(private_key.public_key(), digest, envelope)


def test_wrong_key_fails(signature: SignatureEnvelope) -> None:
    stranger = generate_private_key().public_key()
    assert not verify_signature(stranger, DIGEST, signature)


def test_wrong_digest_fails(
    public_key: Ed25519PublicKey, signature: SignatureEnvelope
) -> None:
    assert not verify_signature(public_key, OTHER_DIGEST, signature)


@pytest.mark.parametrize("index", [0, 1, 31, 63])
def test_corrupt_signature_fails(
    public_key: Ed25519PublicKey, signature: SignatureEnvelope, index: int
) -> None:
    assert not verify_signature(public_key, DIGEST, corrupt(signature, index=index))


def test_truncated_signature_fails(
    public_key: Ed25519PublicKey, signature: SignatureEnvelope
) -> None:
    raw = base64.b64decode(signature.signature)[:32]
    truncated = SignatureEnvelope(
        algorithm="ed25519",
        key_id=KEY_ID,
        signature=base64.b64encode(raw).decode("ascii"),
    )
    assert not verify_signature(public_key, DIGEST, truncated)


def test_an_all_zero_signature_fails(public_key: Ed25519PublicKey) -> None:
    forged = SignatureEnvelope(
        algorithm="ed25519",
        key_id=KEY_ID,
        signature=base64.b64encode(bytes(ED25519_SIGNATURE_BYTES)).decode("ascii"),
    )
    assert not verify_signature(public_key, DIGEST, forged)


def test_swapping_the_key_id_does_not_make_a_signature_valid(
    signature: SignatureEnvelope,
) -> None:
    # ``key_id`` is a routing label. Changing it must not change the outcome of
    # verification, which depends only on the key and the digest.
    relabelled = SignatureEnvelope(
        algorithm="ed25519",
        key_id="someone-else",
        signature=signature.signature,
    )
    stranger = generate_private_key().public_key()
    assert not verify_signature(stranger, DIGEST, relabelled)


@pytest.mark.parametrize(
    "digest",
    [
        "ab" * 32,
        f"{DIGEST_PREFIX}{('ab' * 32).upper()}",
        f"{DIGEST_PREFIX}{'ab' * 31}",
        "",
    ],
)
def test_signing_a_malformed_digest_fails(
    private_key: Ed25519PrivateKey, digest: str
) -> None:
    with pytest.raises(ValidationError, match="digest must be"):
        sign_digest(private_key, digest, key_id=KEY_ID)


def test_verifying_against_a_malformed_digest_fails(
    public_key: Ed25519PublicKey, signature: SignatureEnvelope
) -> None:
    with pytest.raises(ValidationError, match="digest must be"):
        verify_signature(public_key, "not-a-digest", signature)


@pytest.mark.parametrize("key_id", ["", "   "])
def test_signing_requires_a_key_id(private_key: Ed25519PrivateKey, key_id: str) -> None:
    with pytest.raises(PydanticValidationError):
        sign_digest(private_key, DIGEST, key_id=key_id)


# ---------------------------------------------------------------------------
# Package-level prohibitions, spec sections 2.6 and 2.7
# ---------------------------------------------------------------------------


def package_modules() -> list[Path]:
    """Every ordinary package module.

    ``resources/`` is excluded: the managed engine bundle is a separate,
    independently locked environment that is allowed to depend on Verifiers.
    """
    resources = PACKAGE_ROOT / "resources"
    return sorted(
        path
        for path in PACKAGE_ROOT.rglob("*.py")
        if not path.is_relative_to(resources)
    )


def imported_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


FORBIDDEN_IMPORT_ROOTS = frozenset({"verifiers", "hermes", "nemo", "nemo_rl", "relay"})

#: The names that would mean a real signing flow exists. Only ``crypto`` itself
#: and this test may mention them.
SIGNING_NAMES = frozenset(
    {
        "generate_private_key",
        "load_private_key",
        "private_key_bytes",
        "sign_digest",
        "Ed25519PrivateKey",
    }
)


def test_the_package_never_imports_verifiers_hermes_or_relay() -> None:
    offenders: dict[str, set[str]] = {}
    for module in package_modules():
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        forbidden = imported_roots(tree) & FORBIDDEN_IMPORT_ROOTS
        if forbidden:
            offenders[str(module.relative_to(PACKAGE_ROOT))] = forbidden
    assert offenders == {}


def test_no_module_outside_crypto_reaches_for_a_signing_primitive() -> None:
    offenders: dict[str, set[str]] = {}
    for module in package_modules():
        if module.name == "crypto.py":
            continue
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        used = {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name) and node.id in SIGNING_NAMES
        }
        used |= {
            alias.asname or alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
            if alias.name in SIGNING_NAMES
        }
        if used:
            offenders[str(module.relative_to(PACKAGE_ROOT))] = used
    assert offenders == {}


def test_crypto_stores_nothing() -> None:
    # No key store exists here by design, so the module must not import any
    # means of writing one.
    tree = ast.parse((PACKAGE_ROOT / "crypto.py").read_text(encoding="utf-8"))
    storage_roots = {"os", "pathlib", "shutil", "tempfile", "sqlite3", "keyring"}
    assert imported_roots(tree) & storage_roots == set()
    assert "techtree.fs" not in (PACKAGE_ROOT / "crypto.py").read_text(encoding="utf-8")
