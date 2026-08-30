"""One turn is one subject generation that produced a reply. Decision 0029.

The compiler maps the Campaign's ``maximum_model_calls`` onto the engine's
``max_turns``. Compiling one to the other is only honest if the two count the
same events for the pinned profile, and nothing about the names guarantees
that: a harness that made two generations inside one turn would be capped at
twice the calls a publisher declared, and nobody would see it. So the mapping
is checked against evidence rather than against a reading of the engine.

Decision 0029's binding interpretation of what is counted:

    One Verifiers turn is one subject-model generation THAT PRODUCED A REPLY.
    An exchange the provider rejected — an upstream rate limit, a dropped
    connection — produced no reply and no usage, and is therefore neither
    counted as a turn nor billed.

That reading is the one ``release/limit-calibration.json`` records over the
canonical corpus, where replying generations equalled ``Trace.num_turns`` in
731 of 731 episodes while the raw exchange count exceeded it in 27. The raw
count is the interception layer's own log of every HTTP exchange it saw,
rejections included, so it is an upper bound on turns and never the mapping.

The two counts a normalized episode carries cannot separate the two readings:
``model_calls`` is the length of the raw call list and ``num_turns`` is what
the trace computed, and a rejected exchange is invisible in the difference.
The separation lives in the raw ``traces.jsonl`` the engine writes beside the
normalized file, whose every call records whether the exchange errored. So:

* With the raw file beside it, each trace is checked strictly — ``num_turns``
  against the number of intercepted exchanges that completed without error —
  and any disagreement is a real one that fails the check.
* Without it, the only claim the evidence supports is the bound
  ``num_turns <= model_calls``. Breaking the bound fails; satisfying it is
  reported as a bound, never as a pass on the strict mapping.

If the strict check fails, the answer is a new ``maximum_turns`` Campaign
field with ``maximum_model_calls`` left unsupported until v0.2. Never a
silent mapping.

Run it over the recorded canonical evidence, or over the normalized output of
a fresh comparison::

    python tools/verify_turn_conformance.py tests/fixtures/receipts/recorded
    python tools/verify_turn_conformance.py ~/.techtree/runs/run_x/verifiers

Exit status is 0 when every trace holds and at least one trace was read, and
1 otherwise. A run with nothing in it proves nothing and is not a pass.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: What the engine's normalizer writes for one variant.
EPISODES_FILENAME = "normalized-episodes.jsonl"

#: The engine's own trace log, written beside the normalized episodes. Its
#: call records are the only place a rejected exchange can be told from a
#: generation that answered.
RAW_FILENAME = "traces.jsonl"


def produced_a_reply(call: dict[str, Any]) -> bool:
    """Whether this intercepted exchange came back with a generation.

    A rejected exchange records the provider's error and nothing else: no
    node, no finish reason, no usage. This is the predicate decision 0029's
    reading turns on, and the one ``release/limit-calibration.json`` measured
    the canonical corpus with.
    """
    return call.get("error") is None


@dataclass(frozen=True)
class Disagreement:
    """One trace whose turn count the evidence does not support."""

    source: str
    episode_id: str
    trace_id: str
    detail: str

    def describe(self) -> str:
        """Return one line naming the trace and what was wrong with it."""
        return (
            f"{self.source}: episode {self.episode_id} trace "
            f"{self.trace_id} {self.detail}"
        )


@dataclass
class Conformance:
    """What the evidence said about turns, generations and rejections."""

    #: Traces checked strictly, against the raw call list behind them.
    strict_traces: int = 0
    #: Traces for which only ``num_turns <= model_calls`` could be checked.
    bounded_traces: int = 0
    files: list[str] = field(default_factory=list)
    disagreements: list[Disagreement] = field(default_factory=list)
    #: Exchanges the provider rejected, by error type, over strict files.
    rejected: Counter[str] = field(default_factory=Counter)
    #: Replying generations whose usage the provider did not report.
    unmetered: int = 0
    #: One line per file that had no raw traces beside it.
    unverifiable: list[str] = field(default_factory=list)

    @property
    def traces(self) -> int:
        """How many subject traces were read at all."""
        return self.strict_traces + self.bounded_traces

    @property
    def ok(self) -> bool:
        """Whether the mapping holds, over evidence that actually exists."""
        return self.traces > 0 and not self.disagreements

    def describe(self) -> str:
        """Return the verdict, in the words the decision is written in."""
        if not self.traces:
            return "no normalized episodes were found, so nothing was checked"
        return "\n".join([*self._verdict(), *self._info()])

    def _verdict(self) -> list[str]:
        """Return the pass or fail lines, one status per line."""
        if self.disagreements:
            return [
                f"failed  turn_conformance: {len(self.disagreements)} of "
                f"{self.traces} traces disagree; maximum_model_calls must "
                "not compile to max_turns",
                *(f"        {item.describe()}" for item in self.disagreements),
            ]
        lines = []
        if self.strict_traces:
            lines.append(
                f"passed  turn_conformance: {self.strict_traces} traces in "
                f"{len(self.files)} files: every turn is one subject "
                "generation that produced a reply"
            )
        if self.bounded_traces:
            lines.append(
                f"passed  turn_bound: {self.bounded_traces} traces in "
                f"{len(self.files)} files: num_turns never exceeds model_calls"
            )
        return lines

    def _info(self) -> list[str]:
        """Return what the evidence says that no verdict turns on."""
        lines = []
        if self.rejected:
            kinds = ", ".join(
                f"{count} {kind}" for kind, count in sorted(self.rejected.items())
            )
            lines.append(
                f"info    provider_rejected_exchanges: "
                f"{sum(self.rejected.values())} intercepted exchanges were "
                f"rejected by the provider ({kinds}); they produced no reply "
                "and no usage, so decision 0029 counts them as neither turns "
                "nor billed tokens"
            )
        if self.unmetered:
            lines.append(
                f"info    unmetered_generations: {self.unmetered} generations "
                "produced a reply but carry no usage record, so they are "
                "turns whose tokens the provider did not report"
            )
        lines.extend(
            f"info    unverifiable_without_raw: {line}" for line in self.unverifiable
        )
        return lines


def episode_files(paths: list[Path]) -> list[Path]:
    """Return every normalized-episode file under the given paths, in order."""
    found: list[Path] = []
    for path in paths:
        if path.is_dir():
            found.extend(sorted(path.rglob(EPISODES_FILENAME)))
        elif path.is_file():
            found.append(path)
    return found


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Return every record in a JSON-lines file, blank lines skipped."""
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def raw_calls(path: Path) -> dict[tuple[str, str], list[dict[str, Any]]]:
    """Return every raw trace's call list, keyed by episode and trace id.

    The raw record's ``id`` is the normalized episode id and each raw trace's
    ``id`` is the normalized ``trace_id``; the two files hold the same traces
    in different orders, so they are matched by those ids and never by
    position.
    """
    return {
        (episode["id"], trace["id"]): trace["calls"]
        for episode in read_jsonl(path)
        for trace in episode["traces"]
    }


def check(paths: list[Path]) -> Conformance:
    """Check every subject trace the given paths hold, against its evidence."""
    result = Conformance()
    for path in episode_files(paths):
        result.files.append(str(path))
        raw_path = path.parent / RAW_FILENAME
        if raw_path.is_file():
            _check_strictly(result, path, raw_calls(raw_path))
        else:
            _check_the_bound(result, path)
    return result


def _check_strictly(
    result: Conformance,
    path: Path,
    calls_by_trace: dict[tuple[str, str], list[dict[str, Any]]],
) -> None:
    """Compare each trace's turns against the generations that answered."""
    for episode in read_jsonl(path):
        for trace in episode["traces"]:
            result.strict_traces += 1
            key = (episode["episode_id"], trace["trace_id"])
            calls = calls_by_trace.get(key)
            if calls is None:
                result.disagreements.append(
                    Disagreement(
                        source=str(path),
                        episode_id=key[0],
                        trace_id=key[1],
                        detail=(
                            f"has no trace of its own in {RAW_FILENAME}, so "
                            "its turn count stands on nothing"
                        ),
                    )
                )
                continue
            replies = 0
            for call in calls:
                if not produced_a_reply(call):
                    result.rejected[str(call["error"]["type"])] += 1
                    continue
                replies += 1
                if not call.get("usage"):
                    result.unmetered += 1
            if replies != trace["num_turns"]:
                result.disagreements.append(
                    Disagreement(
                        source=str(path),
                        episode_id=key[0],
                        trace_id=key[1],
                        detail=(
                            f"made {replies} generations that produced a "
                            f"reply across {trace['num_turns']} turns"
                        ),
                    )
                )


def _check_the_bound(result: Conformance, path: Path) -> None:
    """Check the only claim a normalized file alone can support."""
    unaccounted = 0
    traces = 0
    for episode in read_jsonl(path):
        for trace in episode["traces"]:
            result.bounded_traces += 1
            traces += 1
            unaccounted += trace["model_calls"] - trace["num_turns"]
            if trace["num_turns"] > trace["model_calls"]:
                result.disagreements.append(
                    Disagreement(
                        source=str(path),
                        episode_id=episode["episode_id"],
                        trace_id=trace["trace_id"],
                        detail=(
                            f"counted {trace['num_turns']} turns over only "
                            f"{trace['model_calls']} intercepted exchanges, "
                            "which no reading of the mapping allows"
                        ),
                    )
                )
    result.unverifiable.append(
        f"{path}: {traces} traces, {unaccounted} intercepted exchanges beyond "
        f"the turn count; no {RAW_FILENAME} sits beside this file, so whether "
        "those were provider rejections or extra generations is unknown and "
        "only the bound num_turns <= model_calls was checked here"
    )


def main(argv: list[str] | None = None) -> int:
    """Check the evidence named on the command line and report the verdict."""
    parser = argparse.ArgumentParser(
        prog="verify_turn_conformance",
        description=(
            "Check that every subject trace made one replying generation per "
            "turn, which is what makes maximum_model_calls compile to "
            "max_turns (decision 0029)."
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
