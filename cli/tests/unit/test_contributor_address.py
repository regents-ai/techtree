"""The one thing that is checked about a volunteered address. Decisions 0038.

An address is optional, unverifiable, and unrecoverable if it is wrong. Nobody
proves control of it and nothing here pretends otherwise; what these tests hold
is the narrow thing that *can* be established from forty characters, which is
that they are forty characters of the right kind and that, where the person who
typed them wrote them in mixed case, the checksum hidden in that case agrees.

The vectors are EIP-55's own, and the Keccak vectors underneath them are the
published ones. Both are here because the checksum is worth nothing if the hash
under it is the wrong hash — ``hashlib.sha3_256`` would produce a perfectly
consistent checksum that every wallet in the world disagrees with.
"""

from __future__ import annotations

import pytest

from techtree.errors import ValidationError
from techtree.publication.address import (
    CONTRIBUTOR_ADDRESS_INVALID,
    canonical_contributor_address,
    eip55_checksum,
)
from techtree.publication.keccak import keccak256

# ---------------------------------------------------------------------------
# The hash underneath
# ---------------------------------------------------------------------------

#: The published Keccak-256 vectors. The empty-string one is the value every
#: Ethereum implementation carries as a constant, which makes it the fastest
#: way to see that this is Keccak and not SHA-3.
KECCAK_VECTORS: tuple[tuple[bytes, str], ...] = (
    (b"", "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"),
    (b"abc", "4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45"),
    (
        b"The quick brown fox jumps over the lazy dog",
        "4d741b6f1eb29cb2a9b9911c82f56fa8d73b04959d3d9d222895df6c0b28aa15",
    ),
)


@pytest.mark.parametrize(("message", "digest"), KECCAK_VECTORS)
def test_the_hash_is_keccak(message: bytes, digest: str) -> None:
    assert keccak256(message).hex() == digest


def test_the_hash_is_not_sha3() -> None:
    """The one-byte difference that would break every checksum silently."""
    import hashlib

    assert keccak256(b"") != hashlib.sha3_256(b"").digest()


def test_a_message_longer_than_the_rate_absorbs_more_than_one_block() -> None:
    """The sponge's second block, which a short vector never reaches.

    Keccak-256 absorbs 136 bytes at a time. A test that only ever hashed forty
    characters would never permute twice, and the loop that does it would be
    untested in the one function this module exists for.
    """
    assert keccak256(b"a" * 200).hex() == (
        "96ea54061def936c4be90b518992fdc6f12f535068a256229aca54267b4d084d"
    )


# ---------------------------------------------------------------------------
# The checksum
# ---------------------------------------------------------------------------

#: EIP-55's own worked examples: two written in one case, which carry no
#: checksum at all, and four in mixed case, which do.
ONE_CASE: tuple[str, ...] = (
    "0x52908400098527886E0F7030069857D2E4169EE7",
    "0x8617E340B3D01FA5F11F306F4090FD50E238070D",
    "0xde709f2102306220921060314715629080e2fb77",
    "0x27b1fdb04752bbc536007a920d24acb045561c26",
)

CHECKSUMMED: tuple[str, ...] = (
    "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed",
    "0xfB6916095ca1df60bB79Ce92cE3Ea74c37c5d359",
    "0xdbF03B407c01E7cD3CBea99509d93f8DDDC8C6FB",
    "0xD1220A0cf47c7B9Be7A2E6BA89F429762e7b9aDb",
)


@pytest.mark.parametrize("address", CHECKSUMMED)
def test_the_checksum_reproduces_the_published_spelling(address: str) -> None:
    assert eip55_checksum(address.lower()) == address


@pytest.mark.parametrize("address", CHECKSUMMED + ONE_CASE)
def test_a_well_formed_address_is_accepted_and_lowercased(address: str) -> None:
    """What travels is one canonical form, so an address is one key."""
    assert canonical_contributor_address(address) == address.lower()


@pytest.mark.parametrize("address", CHECKSUMMED)
def test_one_character_of_the_wrong_case_is_refused(address: str) -> None:
    """A mistyped address is unrecoverable, and the check is free.

    The mistake this catches is the realistic one: not a mangled string but a
    single character read or copied wrongly. Flipping the case of one letter is
    exactly what that looks like to the checksum.
    """
    flipped_any = False
    for position in range(2, len(address)):
        character = address[position]
        if not character.isalpha():
            continue
        flipped_any = True
        flipped = (
            address[:position]
            + (character.lower() if character.isupper() else character.upper())
            + address[position + 1 :]
        )
        with pytest.raises(ValidationError) as raised:
            canonical_contributor_address(flipped)
        assert raised.value.details["reason"] == "checksum", flipped
    assert flipped_any


def test_an_address_in_one_case_carries_no_checksum_to_be_wrong_about() -> None:
    """Lowercase hexadecimal is the address with the checksum stripped off."""
    checksummed = CHECKSUMMED[0]

    assert canonical_contributor_address(checksummed.lower()) == checksummed.lower()
    assert canonical_contributor_address(checksummed.upper().replace("0X", "0x")) == (
        checksummed.lower()
    )


def test_surrounding_whitespace_is_trimmed() -> None:
    """An address arrives pasted, and a paste brings its neighbours with it."""
    assert canonical_contributor_address(f"  {CHECKSUMMED[0]}\n") == (
        CHECKSUMMED[0].lower()
    )


@pytest.mark.parametrize(
    "typed",
    [
        "",
        "0x",
        "5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed",
        "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAe",
        "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAedd",
        "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAeZ",
        "vitalik.eth",
        "0x5aAeb6053F3E94C9b9A09f3366 9435E7Ef1BeAed",
    ],
)
def test_anything_that_is_not_forty_hexadecimal_characters_is_refused(
    typed: str,
) -> None:
    with pytest.raises(ValidationError) as raised:
        canonical_contributor_address(typed)

    assert raised.value.code == CONTRIBUTOR_ADDRESS_INVALID
    assert raised.value.details["reason"] == "shape"


def test_a_refusal_never_repeats_the_address_back() -> None:
    """A refusal that echoed it would put it in the envelope and the scrollback.

    The whole rule about a volunteered address is that it is sent and not kept.
    An error message is a place it would be kept, so the refusal describes the
    shape of what was typed and never the characters.
    """
    typed = "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAeD"

    with pytest.raises(ValidationError) as raised:
        canonical_contributor_address(typed)

    rendered = f"{raised.value.message} {raised.value.details}"
    assert typed not in rendered
    assert typed.lower() not in rendered.lower()
