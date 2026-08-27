# Generate the golden fixture that pins this repository's canonical JSON
# encoder to the one `techtree-python` signs with.
#
#     uv run --project ../techtree-python python scripts/generate_canonical_fixture.py \
#       --proof "$HOME/Library/Application Support/techtree/runs/<run>/proof" \
#       --golden ../techtree-python/tests/golden
#
# Nothing here is hand-written. Every expected byte string in the fixture is
# produced by the same encoder the protocol digests are taken over, so a
# disagreement between the two implementations is a test failure rather than a
# rejected submission in production.
#
# Three things are written:
#
#   * `documents/` and `expected/` — each golden document, and exactly what the
#     Python encoder makes of it. These documents are pretty-printed, so they
#     exercise the re-encoding path rather than an identity.
#   * `already-canonical.json` — the proof-bundle files whose own bytes the
#     Python encoder reproduces exactly. The Elixir test asserts that this list
#     covers every JSON file in the bundle fixture, so a file that stopped being
#     canonical could not silently drop out of the check.
#   * `numbers.json` — one-element JSON arrays around numbers chosen to sit on
#     every boundary in the ECMAScript number-to-string rules, plus a spread of
#     random doubles taken from raw bit patterns.

from __future__ import annotations

import argparse
import json
import math
import random
import shutil
import struct
from pathlib import Path

import rfc8785

FIXTURES = Path(__file__).resolve().parent.parent / "test" / "support" / "fixtures"

BOUNDARY_NUMBERS: list[float | int] = [
    0.0,
    -0.0,
    1.0,
    -1.0,
    0.5,
    -0.5,
    1e21,
    1e20,
    1e22,
    -1e21,
    1e-6,
    1e-7,
    1e-5,
    0.0001,
    1e16,
    1e17,
    123456789012345678.0,
    0.6388888888888888,
    525.584169,
    0.0016057909233495593,
    5e-324,
    2.2250738585072014e-308,
    1.7976931348623157e308,
    9007199254740991,
    -9007199254740991,
    0,
    -1,
    1,
    100,
    1e-320,
    3.141592653589793,
    2.718281828459045,
    1e300,
    1.5e-10,
]


def write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def golden_documents(golden: Path, destination: Path) -> int:
    documents = destination / "documents"
    expected = destination / "expected"
    for stale in (documents, expected):
        if stale.exists():
            shutil.rmtree(stale)

    count = 0
    for source in sorted(golden.glob("*.json")):
        raw = source.read_bytes()
        write(documents / source.name, raw)
        write(expected / (source.stem + ".canonical"), rfc8785.dumps(json.loads(raw)))
        count += 1
    return count


def proof_bundle(proof: Path, destination: Path) -> tuple[int, list[str]]:
    bundle = destination / "proof"
    if bundle.exists():
        shutil.rmtree(bundle)

    canonical: list[str] = []
    count = 0
    for source in sorted(proof.rglob("*")):
        if not source.is_file():
            continue
        relative = source.relative_to(proof)
        raw = source.read_bytes()
        write(bundle / relative, raw)
        count += 1
        if source.suffix == ".json" and rfc8785.dumps(json.loads(raw)) == raw:
            canonical.append(relative.as_posix())
    return count, canonical


def numbers() -> list[dict[str, str]]:
    values: list[float | int] = list(BOUNDARY_NUMBERS)

    generator = random.Random(20260827)
    while len(values) < 1024:
        candidate = struct.unpack("<d", generator.getrandbits(64).to_bytes(8, "little"))[0]
        if math.isnan(candidate) or math.isinf(candidate):
            continue
        values.append(candidate)

    # Each case is a whole JSON document, so the Elixir side parses it the way
    # it parses a submission. Two spellings of the same number are recorded
    # where they differ: the one Python writes by default, which is often not
    # canonical, and the canonical one, which must re-encode to itself.
    cases = []
    for value in values:
        expected = rfc8785.dumps([value]).decode("utf-8")
        for source in dict.fromkeys([json.dumps([value]), expected]):
            cases.append({"source": source, "expected": expected})
    return cases


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proof", required=True, type=Path)
    parser.add_argument("--golden", required=True, type=Path)
    arguments = parser.parse_args()

    destination = FIXTURES / "canonical"
    documents = golden_documents(arguments.golden, destination)
    files, canonical = proof_bundle(arguments.proof, FIXTURES)

    write(
        destination / "already-canonical.json",
        json.dumps(canonical, indent=2, sort_keys=True).encode("utf-8") + b"\n",
    )
    write(
        destination / "numbers.json",
        json.dumps(numbers(), indent=2).encode("utf-8") + b"\n",
    )

    print(f"golden documents: {documents}")
    print(f"proof bundle files: {files}, canonical json: {len(canonical)}")


if __name__ == "__main__":
    main()
