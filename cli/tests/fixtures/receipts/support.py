"""Recorded evaluation evidence the WP7 receipt tests are built on.

Every episode, reward, runtime record and resolved configuration under
``recorded/`` was produced by a real Verifiers evaluation of a real subject
model in real Docker containers, paid for, on 2026-08-13. Nothing in it is
invented, and nothing in it is recomputed when a test runs: the tests read what
the evaluation left behind and check what Techtree makes of it.

WHERE IT CAME FROM

WP6c executed the full thirty-six-task concurrent comparison and recorded it in
a pytest temporary home, which the operating system has since reclaimed. What
survives on disk, and what is frozen here, is the pair of *paid probes* from
the same day, the same subject model (``qwen/qwen3.7-flash``), the same pinned
engine and the same pipeline that produced the full run:

``baseline``
    two tasks, no Skill, ``exact_match`` 0/2.
``candidate``
    two tasks, the ``branch-code-v1`` Skill mounted, ``exact_match`` 2/2.

They are two separate probe runs rather than two variants of one run, so each
carries its own run request, its own experiment manifest and its own committed
membership, and they are used that way. Both cover the same two tasks, and the
only difference between the two recorded configurations is the mounted Skill —
which is what the Climb measures.

The baseline probe recorded a third episode and no longer carries it. Decisions
document 0012 replaced nine inputs in the introductory membership, and one of
them was the task that episode scored, so it became evidence about a task that
does not exist. ``recorded/provenance.json`` records the removal beside every
other thing about this evidence that is not a raw measurement.

WHAT IS RECORDED AND WHAT IS DERIVED

Recorded, as the run produced it:

* ``normalized-episodes.jsonl`` — written by the pinned engine's own
  normalizer, run over the raw ``traces.jsonl`` those probes wrote. Techtree
  never reads a raw upstream record, so this is the evidence the receipt code
  is supposed to see.
* ``config.toml`` — the configuration the engine resolved and wrote back out,
  byte for byte.
* ``campaign.json``, ``experiment.json``, ``request.json`` — the run's own
  staged copies of what it executed.
* the artifact digests and sizes in ``execution.json``, each hashed from the
  real file, including the raw ``traces.jsonl`` that is deliberately *not*
  committed here: it is hundreds of kilobytes of complete subject transcripts
  and it holds the taskset's expected answers, so it stays local exactly as
  spec section 6.19 requires.

Derived, and named as such: the operational envelope in
``execution.json``'s ``child_outcome``. The argv digest and the start instant
are the ones the child itself wrote into the first line of its ``stderr.log``;
the finish instant is when the child last wrote to its capture files; the exit
code is zero because every committed task produced a complete scored episode.
None of it is scientific — spec section 6.15 calls the child record
operational — and no test asserts anything about the experiment from it.

WHAT WAS RE-PROJECTED, AND WHY

Decisions document 0007 R5 and R9 changed three shapes these probes predate: a
Campaign pins its subject container per platform, a normalized trace carries the
sampling settings it ran under and the number of model calls it made, and a
normalized runtime carries the image index digest its reference names. The raw
``traces.jsonl`` was never retained, so the projection cannot be recomputed from
its source; it was re-projected in place instead, and ``recorded/provenance.json``
records field by field what each new value was derived from.

One of them is not a measurement and is labelled as such there: the projection
that wrote this evidence recorded no per-trace call list, so ``model_calls``
carries the trace's own ``num_turns`` as the closest count the recording can
account for. Nothing asserts on it, and re-recording these probes replaces it
with the real figure.

The subject platform is derived the same way: these probes ran on a darwin/arm64
workstation, so the daemon served the pinned image index as ``linux/arm64``, and
that is what :attr:`RecordedVariant.image_resolution` reports.

WHY THE NORMALIZED PROJECTION CARRIES NO SECRET

Checked rather than assumed, and re-checked by
``test_recorded_evidence_carries_no_secret``. A normalized episode holds an
episode identifier, an environment identifier, a task hash, a position, an
ok flag, digests of the raw records, and one subject trace made of: role, ids,
the Verifiers build, the model and harness identifiers, the bundled-skill flag,
skill digests, the runtime record, tools *by digest*, rewards, metrics, token
counts, turn count, the subject's final reply and any errors. There is no
credential, no endpoint, no request, no transcript and no task data — the task
prompt and its expected answer stay in the raw record, which is why the raw
record stays local. The one piece of model-authored text is ``last_reply``,
the subject's own final message.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from techtree.canonical import digest_object, sha256_digest_bytes
from techtree.models.base import ArtifactRef, Digest
from techtree.models.campaign import CampaignSpec
from techtree.models.experiment import ExperimentManifest
from techtree.models.run import RunRequest
from techtree.receipts.episode import read_variant_episodes
from techtree.receipts.observed import read_resolved_config
from techtree.verifiers.models import (
    ChildProcessOutcome,
    NormalizedEpisode,
    SubjectImageResolution,
    VariantExecutionResult,
    VariantName,
)

__all__ = [
    "NORMALIZED_EPISODES_FILE",
    "RESOLVED_CONFIG_FILE",
    "RecordedVariant",
    "recorded_platform",
    "recorded_root",
    "recorded_variant",
]

NORMALIZED_EPISODES_FILE: Final = "normalized-episodes.jsonl"
RESOLVED_CONFIG_FILE: Final = "config.toml"

_EXECUTION_FILE: Final = "execution.json"
_MEMBERSHIP_FILE: Final = "membership.json"
_CAMPAIGN_FILE: Final = "campaign.json"
_EXPERIMENT_FILE: Final = "experiment.json"
_PROVENANCE_FILE: Final = "provenance.json"
_REQUEST_FILE: Final = "request.json"


@dataclass(frozen=True)
class RecordedVariant:
    """One variant's recorded evaluation, loaded and self-checked."""

    variant: VariantName
    directory: Path
    request: RunRequest
    campaign: CampaignSpec
    experiment: ExperimentManifest
    ordered_task_hashes: list[Digest]
    episodes: list[NormalizedEpisode]
    result: VariantExecutionResult
    resolved_config: dict[str, Any]
    image_resolution: SubjectImageResolution

    @property
    def normalized_episodes_path(self) -> Path:
        """Where the engine's own projection of this variant lives."""
        return self.directory / NORMALIZED_EPISODES_FILE

    @property
    def resolved_config_path(self) -> Path:
        """Where the configuration the engine resolved lives."""
        return self.directory / RESOLVED_CONFIG_FILE

    @property
    def primary_reward(self) -> str:
        """The reward this Campaign's comparison is decided on."""
        return self.campaign.scoring.primary_reward


def recorded_root() -> Path:
    """Return the directory holding the recorded evaluation evidence."""
    return Path(__file__).resolve().parent / "recorded"


def recorded_platform() -> str:
    """Return the platform the daemon served these probes' container on.

    Derived rather than recorded, and written down in ``provenance.json`` so
    the derivation is read from the fixture rather than repeated in code.
    """
    document = json.loads((recorded_root() / _PROVENANCE_FILE).read_text("utf-8"))
    platform: str = document["subject_platform"]
    return platform


def recorded_variant(variant: VariantName) -> RecordedVariant:
    """Load one recorded variant and prove the fixture was not edited.

    The execution record carries the digest of the normalized projection it
    describes, hashed from the file the engine wrote. Re-hashing the committed
    file here means a test can never quietly run against evidence somebody
    adjusted to make an assertion pass.
    """
    directory = recorded_root() / variant.value
    execution = json.loads((directory / _EXECUTION_FILE).read_text(encoding="utf-8"))

    normalized = directory / NORMALIZED_EPISODES_FILE
    recorded_digest = execution["normalized_episodes"]["digest"]
    computed = sha256_digest_bytes(normalized.read_bytes())
    if computed != recorded_digest:
        raise AssertionError(
            f"the recorded {variant.value} episodes no longer hash to the "
            f"digest the execution record names: {computed} != {recorded_digest}"
        )

    experiment = ExperimentManifest.model_validate_json(
        (directory / _EXPERIMENT_FILE).read_bytes()
    )
    if digest_object(experiment) != execution["experiment_manifest_digest"]:
        raise AssertionError(
            f"the recorded {variant.value} manifest is not the one its "
            "execution record names"
        )

    episodes = read_variant_episodes(normalized)
    membership = json.loads((directory / _MEMBERSHIP_FILE).read_text(encoding="utf-8"))
    ordered: list[Digest] = list(membership["ordered_task_hashes"])
    campaign = CampaignSpec.model_validate_json(
        (directory / _CAMPAIGN_FILE).read_bytes()
    )
    runtime = campaign.agents["subject"].runtime
    image_resolution = SubjectImageResolution(
        variant=variant,
        image=runtime.image,
        index_digest=runtime.image_index_digest,
        platform=recorded_platform(),
    )

    return RecordedVariant(
        variant=variant,
        directory=directory,
        request=RunRequest.model_validate_json(
            (directory / _REQUEST_FILE).read_bytes()
        ),
        campaign=campaign,
        experiment=experiment,
        ordered_task_hashes=ordered,
        episodes=episodes,
        image_resolution=image_resolution,
        result=VariantExecutionResult(
            variant=variant,
            experiment_manifest_digest=execution["experiment_manifest_digest"],
            resolved_verifiers_config=_artifact(execution, "resolved_verifiers_config"),
            raw_traces=_artifact(execution, "raw_traces"),
            eval_log=_artifact(execution, "eval_log"),
            normalized_episodes=_artifact(execution, "normalized_episodes"),
            child_outcome=ChildProcessOutcome.model_validate_json(
                json.dumps(execution["child_outcome"])
            ),
            image_resolution=image_resolution,
            episodes=episodes,
        ),
        resolved_config=read_resolved_config(directory / RESOLVED_CONFIG_FILE),
    )


def _artifact(execution: dict[str, Any], name: str) -> ArtifactRef:
    """Return one recorded artifact reference."""
    return ArtifactRef.model_validate_json(json.dumps(execution[name]))
