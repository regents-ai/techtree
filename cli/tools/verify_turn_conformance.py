"""Check that one Verifiers turn is one subject-model call. Decision 0029.

The Campaign declares ``maximum_model_calls`` and the pinned engine enforces
``max_turns``. Compiling one to the other is only honest if the two count the
same events for the pinned profile, and nothing about the names guarantees
that: a harness that made two generations inside one turn would be capped at
twice the calls a publisher declared, and nobody would see it.

So the mapping is checked rather than assumed, against evidence rather than
against a reading of the engine. Every normalized episode carries both numbers
for its subject trace — ``model_calls`` is the length of the interception
layer's own call list, ``num_turns`` is what the trace computed — and they are
produced independently. If any trace disagrees, the mapping is false and the
answer is a new ``maximum_turns`` Campaign field with
``maximum_model_calls`` left unsupported until v0.2. Never a silent mapping.

Run it over the recorded canonical evidence, or over the normalized output of
a fresh comparison::

    python tools/verify_turn_conformance.py tests/fixtures/receipts/recorded
    python tools/verify_turn_conformance.py ~/.techtree/runs/run_x/verifiers

Exit status is 0 when every trace agrees and at least one trace was read, and
1 otherwise. A run with nothing in it proves nothing and is not a pass.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

#: What the engine's normalizer writes for one variant.
EPISODES_FILENAME = "normalized-episodes.jsonl"


@dataclass(frozen=True)
class Disagreement:
    """One trace whose two counts are not the same number."""

    source: str
    episode_id: str
    model_calls: int
    num_turns: int

    def describe(self) -> str:
        """Return one line naming the episode and both counts."""
        return (
            f"{self.source}: episode {self.episode_id} made "
            f"{self.model_calls} model calls across {self.num_turns} turns"
        )


@dataclass
class Conformance:
    """What every trace in the evidence said about turns and calls."""

    traces: int = 0
    files: list[str] = field(default_factory=list)
    disagreements: list[Disagreement] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Whether the mapping holds, over evidence that actually exists."""
        return self.traces > 0 and not self.disagreements

    def describe(self) -> str:
        """Return the verdict, in the words the decision is written in."""
        if not self.traces:
            return "no normalized episodes were found, so nothing was checked"
        if self.disagreements:
            lines = [
                f"{len(self.disagreements)} of {self.traces} traces disagree; "
                "maximum_model_calls must not compile to max_turns",
                *(item.describe() for item in self.disagreements),
            ]
            return "\n".join(lines)
        return (
            f"{self.traces} traces in {len(self.files)} files: every subject "
            "trace made exactly one model call per turn"
        )


def episode_files(paths: list[Path]) -> list[Path]:
    """Return every normalized-episode file under the given paths, in order."""
    found: list[Path] = []
    for path in paths:
        if path.is_dir():
            found.extend(sorted(path.rglob(EPISODES_FILENAME)))
        elif path.is_file():
            found.append(path)
    return found


def check(paths: list[Path]) -> Conformance:
    """Compare both counts on every subject trace the given paths hold."""
    result = Conformance()
    for path in episode_files(paths):
        result.files.append(str(path))
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            episode = json.loads(line)
            for trace in episode["traces"]:
                result.traces += 1
                if trace["model_calls"] != trace["num_turns"]:
                    result.disagreements.append(
                        Disagreement(
                            source=str(path),
                            episode_id=episode["episode_id"],
                            model_calls=trace["model_calls"],
                            num_turns=trace["num_turns"],
                        )
                    )
    return result


def main(argv: list[str] | None = None) -> int:
    """Check the evidence named on the command line and report the verdict."""
    parser = argparse.ArgumentParser(
        prog="verify_turn_conformance",
        description=(
            "Check that every subject trace made one model call per turn, "
            "which is what makes maximum_model_calls compile to max_turns."
        ),
    )
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="normalized-episodes.jsonl files, or directories holding them",
    )
    result = check(parser.parse_args(sys.argv[1:] if argv is None else argv).paths)
    print(result.describe())
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
