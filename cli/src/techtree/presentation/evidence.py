"""Counts read back out of a finished run's own recorded evidence.

Two facts a reader of a result asks for are recorded by every run and carried
by none of its signed documents: how many model turns each side took, and how
often the provider refused a model call. The first is the efficiency finding a
Skill's whole value can sit in; the second is a validity question, because two
sides that met different amounts of throttling did not meet identical
conditions even when both finished.

Neither is added to a signed artifact here. The signed
:class:`~techtree.receipts.execution.ComparisonExecutionRecord` already commits
each side's normalized episodes and raw traces *by digest*, so this reads those
two files back at render time and checks them against the digests the record
already holds. A file that is missing, unreadable, or no longer the file the
record committed yields nothing at all rather than a number: an unchecked count
would be worth less than saying it is unknown.

Only counts leave this module. The files it opens carry prompts, replies and
grader material, and nothing here returns a string taken from either of them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from techtree.canonical import sha256_digest_bytes
from techtree.errors import ValidationError
from techtree.models.experiment import ExperimentVariant
from techtree.receipts.execution import ComparisonExecutionRecord
from techtree.verifiers.models import RunPaths, VariantName
from techtree.verifiers.outputs import TRACES_FILENAME, read_normalized_episodes

__all__ = [
    "RATE_LIMIT_STATUS",
    "RecordedEvidence",
    "VariantEvidence",
    "read_recorded_evidence",
]

#: The status a provider refuses a call with when it is being asked for too
#: much too quickly. Read from the recorded call rather than matched against
#: an error message, because a message is the provider's prose and a status is
#: the provider's answer.
RATE_LIMIT_STATUS: Final = 429


@dataclass(frozen=True)
class VariantEvidence:
    """What one side's own recorded files say it did."""

    model_turns: int
    rollouts: int
    rollouts_completed: int
    rate_limited_calls: int


@dataclass(frozen=True)
class RecordedEvidence:
    """Both sides, read from files the signed record commits by digest."""

    baseline: VariantEvidence
    candidate: VariantEvidence

    @property
    def every_rollout_completed(self) -> bool:
        """Whether every rollout on both sides ran to completion."""
        return all(
            side.rollouts_completed == side.rollouts and side.rollouts > 0
            for side in (self.baseline, self.candidate)
        )


def read_recorded_evidence(
    run_root: Path, record: ComparisonExecutionRecord
) -> RecordedEvidence | None:
    """Return both sides' counts, or ``None`` when they cannot be trusted.

    ``None`` is returned for every reason a reading can fail — a run whose
    evaluation output has been cleared away, a file that no longer hashes to
    what the record committed, a line that does not parse. There is no partial
    answer: a result that showed one side's turns and not the other's would
    invite exactly the comparison it could not support.
    """
    paths = RunPaths(root=run_root)
    sides = {}
    for variant in (VariantName.BASELINE, VariantName.CANDIDATE):
        summary = record.side(ExperimentVariant(variant.value))
        side = _variant_evidence(
            paths=paths,
            variant=variant,
            normalized_episodes_digest=summary.normalized_episodes_digest,
            raw_traces_digest=summary.raw_traces_digest,
        )
        if side is None:
            return None
        sides[variant] = side
    return RecordedEvidence(
        baseline=sides[VariantName.BASELINE], candidate=sides[VariantName.CANDIDATE]
    )


def _variant_evidence(
    *,
    paths: RunPaths,
    variant: VariantName,
    normalized_episodes_digest: str,
    raw_traces_digest: str,
) -> VariantEvidence | None:
    """Read one side's two committed files, or return nothing."""
    episodes_path = paths.variant_normalized_episodes(variant)
    if _checked(episodes_path, normalized_episodes_digest) is None:
        return None
    try:
        episodes = read_normalized_episodes(episodes_path)
    except ValidationError:
        return None

    traces_path = paths.variant_output_dir(variant) / TRACES_FILENAME
    raw = _checked(traces_path, raw_traces_digest)
    if raw is None:
        return None
    rate_limited = _rate_limited_calls(raw)
    if rate_limited is None:
        return None

    rollouts = [trace for episode in episodes for trace in episode.traces]
    return VariantEvidence(
        model_turns=sum(trace.num_turns for trace in rollouts),
        rollouts=len(rollouts),
        rollouts_completed=sum(1 for trace in rollouts if trace.ok),
        rate_limited_calls=rate_limited,
    )


def _checked(path: Path, digest: str) -> bytes | None:
    """Return a file's bytes when they are still the bytes that were signed."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    return data if sha256_digest_bytes(data) == digest else None


def _rate_limited_calls(raw: bytes) -> int | None:
    """Count the model calls the provider refused with a rate limit.

    The raw trace records one entry per model call, and a call the provider
    turned away carries the status it was turned away with. Counting the
    statuses is all this does; the message beside each one is the provider's
    own prose about a prompt, and it is never read.
    """
    total = 0
    try:
        for line in raw.decode("utf-8").splitlines():
            if not line.strip():
                continue
            for trace in json.loads(line).get("traces") or []:
                for call in trace.get("calls") or []:
                    error = call.get("error")
                    if isinstance(error, dict) and error.get("status_code") == (
                        RATE_LIMIT_STATUS
                    ):
                        total += 1
    except (UnicodeDecodeError, ValueError, AttributeError):
        return None
    return total
