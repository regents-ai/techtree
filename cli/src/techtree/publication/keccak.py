"""Keccak-256, because EIP-55 is defined over it and nothing here provides it.

This module exists for one reason and has one caller. The mixed-case spelling
of an Ethereum address is a checksum, and the checksum is the original Keccak
submission rather than the NIST standard that came out of it. The two differ by
one byte of padding and produce entirely different digests, so ``hashlib``'s
``sha3_256`` cannot be used and quietly produces a checksum that is wrong for
every address. ``cryptography`` exposes SHA-3 and SHAKE and does not expose
Keccak either.

The alternative to sixty lines here is a third-party dependency in a package
whose dependency list is deliberately eight entries long, pulled in so that a
forty-character string can be checked before it is sent. That trade is not
worth making, and the permutation is fixed for ever: Keccak-f[1600] has not
changed since 2011 and cannot, because the digests it produces are what
everything already published is addressed by.

So this is a plain transcription of the permutation, and it is held to the
published vectors in ``tests/unit/test_contributor_address.py`` rather than to
a reading of the code.
"""

from __future__ import annotations

from typing import Final

__all__ = ["keccak256"]

#: Keccak-f[1600] operates on twenty-five 64-bit lanes.
_LANE_BITS: Final = 64
_LANE_MASK: Final = (1 << _LANE_BITS) - 1
_LANE_BYTES: Final = _LANE_BITS // 8

#: The sponge rate for a 256-bit digest: 1600 bits of state less twice the
#: capacity, in bytes.
_RATE_BYTES: Final = (1600 - 2 * 256) // 8

_DIGEST_BYTES: Final = 32

#: The domain separator Keccak pads with. SHA-3 pads with ``0x06`` instead, and
#: that single byte is the whole of the difference between this function and
#: ``hashlib.sha3_256``.
_PAD_BYTE: Final = 0x01
_PAD_FINAL_BIT: Final = 0x80

#: Rotation offsets, indexed ``[x][y]``.
_ROTATIONS: Final[tuple[tuple[int, ...], ...]] = (
    (0, 36, 3, 41, 18),
    (1, 44, 10, 45, 2),
    (62, 6, 43, 15, 61),
    (28, 55, 25, 21, 56),
    (27, 20, 39, 8, 14),
)

_ROUND_CONSTANTS: Final[tuple[int, ...]] = (
    0x0000000000000001,
    0x0000000000008082,
    0x800000000000808A,
    0x8000000080008000,
    0x000000000000808B,
    0x0000000080000001,
    0x8000000080008081,
    0x8000000000008009,
    0x000000000000008A,
    0x0000000000000088,
    0x0000000080008009,
    0x000000008000000A,
    0x000000008000808B,
    0x800000000000008B,
    0x8000000000008089,
    0x8000000000008003,
    0x8000000000008002,
    0x8000000000000080,
    0x000000000000800A,
    0x800000008000000A,
    0x8000000080008081,
    0x8000000000008080,
    0x0000000080000001,
    0x8000000080008008,
)

type _State = list[list[int]]


def keccak256(data: bytes) -> bytes:
    """Return the Keccak-256 digest of ``data``.

    This is the pre-standardisation Keccak that Ethereum addresses, not
    SHA3-256.
    """
    state: _State = [[0] * 5 for _ in range(5)]
    for block in _blocks(data):
        _absorb(state, block)
        _permute(state)
    return _squeeze(state)


def _blocks(data: bytes) -> list[bytes]:
    """Return the padded message as whole rate-sized blocks.

    Keccak's ``pad10*1``: a one bit, as many zero bits as it takes, and a final
    one bit. Written here in the byte order the lanes are read in, which is why
    the two one bits are the low bit of the first pad byte and the high bit of
    the last.
    """
    padded = bytearray(data)
    padded.append(_PAD_BYTE)
    while len(padded) % _RATE_BYTES != 0:
        padded.append(0)
    padded[-1] |= _PAD_FINAL_BIT
    return [
        bytes(padded[start : start + _RATE_BYTES])
        for start in range(0, len(padded), _RATE_BYTES)
    ]


def _absorb(state: _State, block: bytes) -> None:
    """Exclusive-or one block into the rate portion of the state."""
    for position in range(_RATE_BYTES // _LANE_BYTES):
        lane = int.from_bytes(
            block[position * _LANE_BYTES : (position + 1) * _LANE_BYTES],
            "little",
        )
        state[position % 5][position // 5] ^= lane


def _squeeze(state: _State) -> bytes:
    """Return the first 32 bytes of the state, in lane order.

    A 256-bit digest is shorter than the rate, so the sponge never squeezes
    twice and there is no second permutation to perform here.
    """
    out = bytearray()
    position = 0
    while len(out) < _DIGEST_BYTES:
        out += state[position % 5][position // 5].to_bytes(_LANE_BYTES, "little")
        position += 1
    return bytes(out[:_DIGEST_BYTES])


def _permute(state: _State) -> None:
    """Apply the twenty-four rounds of Keccak-f[1600] in place."""
    for constant in _ROUND_CONSTANTS:
        _theta(state)
        state[:] = _rho_and_pi(state)
        _chi(state)
        state[0][0] ^= constant


def _theta(state: _State) -> None:
    columns = [
        state[x][0] ^ state[x][1] ^ state[x][2] ^ state[x][3] ^ state[x][4]
        for x in range(5)
    ]
    parities = [
        columns[(x - 1) % 5] ^ _rotate(columns[(x + 1) % 5], 1) for x in range(5)
    ]
    for x in range(5):
        for y in range(5):
            state[x][y] ^= parities[x]


def _rho_and_pi(state: _State) -> _State:
    moved: _State = [[0] * 5 for _ in range(5)]
    for x in range(5):
        for y in range(5):
            moved[y][(2 * x + 3 * y) % 5] = _rotate(state[x][y], _ROTATIONS[x][y])
    return moved


def _chi(state: _State) -> None:
    previous = [list(column) for column in state]
    for x in range(5):
        for y in range(5):
            state[x][y] = previous[x][y] ^ (
                (~previous[(x + 1) % 5][y] & _LANE_MASK) & previous[(x + 2) % 5][y]
            )


def _rotate(lane: int, places: int) -> int:
    """Return one 64-bit lane rotated left."""
    places %= _LANE_BITS
    return ((lane << places) | (lane >> (_LANE_BITS - places))) & _LANE_MASK
