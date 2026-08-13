"""One receipt per committed task, from recorded evidence. Spec section 7.6.

The input is the engine's own normalized projection of one variant's episodes
and the run's immutable lineage. The output is one
:class:`~techtree.models.episode_receipt.EpisodeReceipt` per task the Campaign
committed to, in committed order, carrying the reward Verifiers recorded and
nothing derived from it.

Three boundaries meet in this module and each is drawn deliberately.

*The evidence boundary.* :func:`read_variant_episodes` is the only door the
normalized file comes through, and it maps every way that file can be unusable
onto the spec section 15 vocabulary: absent evidence is
``evaluation_output_missing``, unreadable evidence is
``evaluation_output_corrupt``, and a reward that is not a number is
``reward_non_finite`` rather than a generic parse failure — a run whose scoring
produced ``NaN`` failed in a specific way and a reader deserves to be told
which.

*The task-hash boundary.* Verifiers spells a task hash as bare hexadecimal and
Techtree spells it as a prefixed digest. The engine's normalizer converts it
once, on the side that read the wire record, and every hash that enters this
module is revalidated as a Techtree digest before it is compared to anything.
A type annotation is a claim about the caller; a commitment other parties are
held to is checked.

*The lineage boundary.* A receipt names the Campaign, the improvement program,
the public context, the DataPolicy, the OutcomeContract, the evaluation backend
and the experiment manifest it was produced under. Every one of those is copied
from the run's own immutable request and the run's own staged manifest, and
every one is required to agree with the others before a receipt is built.
Nothing is defaulted and nothing is re-resolved.

What is *not* a refusal matters as much. An episode that failed, a trace that
errored, a rollout the provider gave up on: those produce receipts with
``score_status`` saying so. The refusals are reserved for evidence that cannot
be joined onto the Campaign's commitment at all, because those are the cases
where continuing would produce a tidy document making a false claim.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from techtree.canonical import (
    canonical_json_bytes,
    digest_object,
    sha256_digest_bytes,
    validate_digest,
)
from techtree.constants import EPISODE_RECEIPT_SCHEMA_VERSION
from techtree.errors import ValidationError, VerificationError
from techtree.models.base import ArtifactRef, Digest, JsonValue
from techtree.models.campaign import SUBJECT_AGENT, EvidenceRequirements
from techtree.models.episode_receipt import (
    EpisodeReceipt,
    EvidenceStatus,
    NamedTraceReceipt,
    ScoreStatus,
    SubjectRuntimeReceipt,
)
from techtree.models.evaluation_backend import EvaluationBackendSpec
from techtree.models.experiment import ExperimentManifest, ExperimentVariant
from techtree.models.run import RunRequest
from techtree.verifiers.models import (
    NormalizedEpisode,
    NormalizedTrace,
    VariantExecutionResult,
    VariantName,
)
from techtree.verifiers.outputs import read_normalized_episodes

__all__ = [
    "EPISODE_COUNT_MISMATCH",
    "EPISODE_RECEIPT_INVALID",
    "EVALUATION_OUTPUT_CORRUPT",
    "EVALUATION_OUTPUT_MISSING",
    "REWARD_MISSING",
    "REWARD_NON_FINITE",
    "TASK_MEMBERSHIP_MISMATCH",
    "TRACE_ROLE_MISMATCH",
    "build_episode_receipt",
    "build_variant_receipts",
    "experiment_variant_of",
    "read_variant_episodes",
]

#: Stable error codes. Spec section 15 fixes the vocabulary; this module is
#: where the evidence-side half of it is raised.
EVALUATION_OUTPUT_MISSING: Final = "evaluation_output_missing"
EVALUATION_OUTPUT_CORRUPT: Final = "evaluation_output_corrupt"
EPISODE_COUNT_MISMATCH: Final = "episode_count_mismatch"
TASK_MEMBERSHIP_MISMATCH: Final = "task_membership_mismatch"
TRACE_ROLE_MISMATCH: Final = "trace_role_mismatch"
REWARD_MISSING: Final = "reward_missing"
REWARD_NON_FINITE: Final = "reward_non_finite"

#: A receipt whose lineage does not hold together. Spec section 15 lists the
#: evidence failures; this is the one that says the *provenance* disagrees,
#: which is a different question and deserves its own code.
EPISODE_RECEIPT_INVALID: Final = "episode_receipt_invalid"

#: How many hexadecimal characters a derived identifier carries, matching the
#: 32 that :mod:`techtree.ids` issues.
_DERIVED_ID_LENGTH: Final = 32

#: The JSON key that makes a non-finite number under it a reward failure
#: rather than a generic corruption.
_REWARD_KEY: Final = "rewards"


def experiment_variant_of(variant: VariantName) -> ExperimentVariant:
    """Return the protocol variant one execution-local variant names.

    Two enumerations spell the same two words: one belongs to the execution
    layer, which schedules children, and one belongs to the protocol, which
    describes manifests and receipts. Converting between them explicitly, in
    one place, keeps the layers separate without letting either drift.
    """
    return ExperimentVariant(variant.value)


# ---------------------------------------------------------------------------
# The evidence boundary
# ---------------------------------------------------------------------------


def read_variant_episodes(path: Path) -> list[NormalizedEpisode]:
    """Read one variant's normalized episodes, or say precisely what is wrong.

    The raw ``traces.jsonl`` is deliberately not an accepted input here. It is
    read once, by the pinned Verifiers build that wrote it, inside the engine
    bundle; this is the only projection Techtree interprets.
    """
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise ValidationError(
            "this variant's normalized evaluation output was not found, so "
            "there is no evidence to build receipts from",
            code=EVALUATION_OUTPUT_MISSING,
            details={"path": str(path)},
        ) from error

    if not raw:
        raise ValidationError(
            "this variant's normalized evaluation output is empty, so no "
            "episode was ever recorded",
            code=EVALUATION_OUTPUT_MISSING,
            details={"path": str(path)},
        )

    _refuse_non_finite_records(raw, path)

    try:
        return read_normalized_episodes(path)
    except ValidationError as error:
        raise ValidationError(
            f"this variant's normalized evaluation output cannot be read: {error}",
            code=EVALUATION_OUTPUT_CORRUPT,
            details=dict(error.details),
        ) from error


def _refuse_non_finite_records(raw: bytes, path: Path) -> None:
    """Refuse a record carrying a number JSON cannot honestly hold.

    ``NaN`` and the infinities are spellable in the JSON Python accepts and are
    not spellable in canonical JSON, so a record carrying one would parse here
    and then fail, confusingly, at the moment a receipt was digested. It is
    caught at the door instead, and a non-finite *reward* is reported as the
    reward failure it is rather than as generic corruption.
    """
    for number, line in enumerate(
        raw.decode("utf-8", errors="replace").splitlines(), 1
    ):
        if not line.strip():
            continue
        try:
            document = json.loads(line)
        except json.JSONDecodeError:
            # Reported with its line number by the parser below, which knows
            # the record shape and can say what was expected.
            return
        pointer = _first_non_finite(document, "")
        if pointer is None:
            continue
        reward = f"/{_REWARD_KEY}/" in pointer
        raise ValidationError(
            (
                f"the reward at {pointer} is not a finite number"
                if reward
                else f"the value at {pointer} is not a finite number"
            ),
            code=REWARD_NON_FINITE if reward else EVALUATION_OUTPUT_CORRUPT,
            details={"path": str(path), "line": number, "pointer": pointer},
        )


def _first_non_finite(value: object, pointer: str) -> str | None:
    """Return the JSON Pointer of the first non-finite number, or nothing."""
    if isinstance(value, bool):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return pointer or "/"
    if isinstance(value, dict):
        for key, item in value.items():
            found = _first_non_finite(item, f"{pointer}/{key}")
            if found is not None:
                return found
        return None
    if isinstance(value, list):
        for index, item in enumerate(value):
            found = _first_non_finite(item, f"{pointer}/{index}")
            if found is not None:
                return found
    return None


# ---------------------------------------------------------------------------
# One receipt
# ---------------------------------------------------------------------------


def build_episode_receipt(
    *,
    run_request: RunRequest,
    variant: VariantName,
    experiment: ExperimentManifest,
    episode: NormalizedEpisode,
    raw_artifacts: VariantExecutionResult,
    evaluation_backend: EvaluationBackendSpec,
    primary_reward: str,
    evidence: EvidenceRequirements,
) -> EpisodeReceipt:
    """Construct one immutable Techtree receipt from one normalized Episode.

    ``primary_reward`` and ``evidence`` are the two Campaign facts a receipt's
    *statuses* depend on: which reward the comparison turns on, and whether the
    Campaign requires runtime evidence this release cannot collect. They are
    passed explicitly rather than by handing this function the whole Campaign,
    because everything else a receipt cites comes from the run's request and
    the run's manifest, and a second source for those would be a second truth.
    """
    _require_lineage(
        run_request=run_request,
        variant=variant,
        experiment=experiment,
        raw_artifacts=raw_artifacts,
        evaluation_backend=evaluation_backend,
    )
    trace = _subject_trace(episode, variant)
    task_hash = validate_digest(episode.task_hash)
    if validate_digest(trace.task_hash) != task_hash:
        raise VerificationError(
            "this episode's subject trace scored a different task than the "
            "episode it belongs to",
            code=TASK_MEMBERSHIP_MISMATCH,
            details={"episode": episode.task_hash, "trace": trace.task_hash},
        )

    episode_digest = validate_digest(episode.raw_episode_digest)
    return EpisodeReceipt(
        schema_version=EPISODE_RECEIPT_SCHEMA_VERSION,
        id=_receipt_id(
            run_id=run_request.run_id, variant=variant, episode_digest=episode_digest
        ),
        run_id=run_request.run_id,
        campaign_spec_digest=run_request.campaign_spec_digest,
        program_ref=run_request.program_ref,
        public_context=run_request.public_context,
        data_policy_digest=run_request.data_policy_digest,
        outcome_contract_digest=run_request.outcome_contract_digest,
        evaluation_backend=evaluation_backend,
        subject_runtime=_subject_runtime(trace),
        variant=experiment_variant_of(variant),
        experiment_manifest_digest=raw_artifacts.experiment_manifest_digest,
        episode_id=episode.episode_id,
        episode_digest=episode_digest,
        task_hash=task_hash,
        named_traces={
            SUBJECT_AGENT: [
                NamedTraceReceipt(
                    role=SUBJECT_AGENT,
                    trace_id=trace.trace_id,
                    trace_digest=validate_digest(trace.raw_trace_digest),
                    task_hash=task_hash,
                    rewards=_recorded_rewards(trace),
                    metrics=_recorded_metrics(trace),
                    ok=trace.ok,
                )
            ]
        },
        score_status=_score_status(episode, trace, primary_reward),
        evidence_status=_evidence_status(trace, evidence),
        execution_backend="verifiers",
        artifacts=_variant_artifacts(raw_artifacts),
    )


def _require_lineage(
    *,
    run_request: RunRequest,
    variant: VariantName,
    experiment: ExperimentManifest,
    raw_artifacts: VariantExecutionResult,
    evaluation_backend: EvaluationBackendSpec,
) -> None:
    """Require every reference a receipt copies to agree with every other."""
    expected_variant = experiment_variant_of(variant)
    configuration = experiment.configuration
    declared_manifest = (
        run_request.baseline_manifest_digest
        if expected_variant is ExperimentVariant.BASELINE
        else run_request.candidate_manifest_digest
    )
    manifest_digest = digest_object(experiment)

    _require(
        raw_artifacts.variant is variant,
        f"a {variant.value} receipt cannot be built from a "
        f"{raw_artifacts.variant.value} execution",
        variant=variant.value,
    )
    _require(
        experiment.variant is expected_variant,
        f"a {variant.value} receipt cannot be built from a "
        f"{experiment.variant.value} manifest",
        variant=variant.value,
    )
    _require(
        manifest_digest == raw_artifacts.experiment_manifest_digest,
        "this execution was produced from a different experiment manifest "
        "than the one the receipt is being built against",
        expected=raw_artifacts.experiment_manifest_digest,
        computed=manifest_digest,
    )
    _require(
        manifest_digest == declared_manifest,
        f"the staged {variant.value} manifest is not the one this run's request names",
        expected=declared_manifest,
        computed=manifest_digest,
    )
    _require(
        experiment.campaign_spec_digest == run_request.campaign_spec_digest,
        "the manifest and the run's request name different Campaigns",
        expected=run_request.campaign_spec_digest,
        computed=experiment.campaign_spec_digest,
    )
    _require(
        configuration.data_policy_digest == run_request.data_policy_digest,
        "the manifest and the run's request name different DataPolicies",
        expected=run_request.data_policy_digest,
        computed=configuration.data_policy_digest,
    )
    _require(
        configuration.outcome_contract_digest == run_request.outcome_contract_digest,
        "the manifest and the run's request name different OutcomeContracts",
    )
    _require(
        experiment.program_ref == run_request.program_ref
        and experiment.public_context == run_request.public_context,
        "the manifest and the run's request name a different improvement "
        "program or public context",
    )
    _require(
        evaluation_backend == run_request.evaluation_backend
        and evaluation_backend == configuration.evaluation_backend,
        "the evaluation backend this receipt would carry is not the one the "
        "run's request and manifest were executed under",
    )


def _require(condition: bool, message: str, **details: str) -> None:
    """Raise a typed lineage refusal unless the condition holds."""
    if condition:
        return
    reported: dict[str, JsonValue] = dict(details)
    raise VerificationError(message, code=EPISODE_RECEIPT_INVALID, details=reported)


def _subject_trace(episode: NormalizedEpisode, variant: VariantName) -> NormalizedTrace:
    """Return the one subject rollout this episode is allowed to carry."""
    traces = [trace for trace in episode.traces if trace.agent_role == SUBJECT_AGENT]
    if len(traces) == 1 and len(episode.traces) == 1:
        return traces[0]
    raise VerificationError(
        f"episode {episode.episode_id} carries {len(episode.traces)} trace(s), "
        f"{len(traces)} of them in the {SUBJECT_AGENT!r} seat; a v0.1 episode "
        "carries exactly one subject trace and nothing else",
        code=TRACE_ROLE_MISMATCH,
        details={
            "variant": variant.value,
            "episode_id": episode.episode_id,
            "traces": len(episode.traces),
            "subject_traces": len(traces),
        },
    )


def _recorded_rewards(trace: NormalizedTrace) -> dict[str, float]:
    """Copy every reward exactly as Verifiers scored it.

    The score, not the weighted value. A weight is the Campaign's opinion about
    how much a reward should count; the score is what the evaluation measured,
    and a receipt records the measurement. The weight and the weighted value
    both survive in the normalized episode the receipt's artifacts point at.
    """
    rewards: dict[str, float] = {}
    for reward in trace.rewards:
        _require_finite(reward.score, f"reward {reward.name!r}", trace)
        rewards[reward.name] = reward.score
    return rewards


def _recorded_metrics(trace: NormalizedTrace) -> dict[str, float | None]:
    """Copy every metric exactly as recorded."""
    for name, value in trace.metrics.items():
        if value is not None:
            _require_finite(value, f"metric {name!r}", trace, reward=False)
    return dict(trace.metrics)


def _require_finite(
    value: float, label: str, trace: NormalizedTrace, *, reward: bool = True
) -> None:
    """Refuse a number a receipt could not be digested with."""
    if math.isfinite(value):
        return
    raise VerificationError(
        f"the {label} recorded on trace {trace.trace_id} is not finite, so it "
        "is not a measurement",
        code=REWARD_NON_FINITE if reward else EVALUATION_OUTPUT_CORRUPT,
        details={"trace_id": trace.trace_id, "value": repr(value)},
    )


def _subject_runtime(trace: NormalizedTrace) -> SubjectRuntimeReceipt:
    """Describe the box the subject actually executed in.

    A Docker receipt must cite the image it ran, and it cites the content the
    pinned reference names. Which platform that content was served on is a fact
    about the machine rather than about the episode, so it lives in the
    comparison's observed configuration and is left unset here.
    """
    return SubjectRuntimeReceipt(
        kind="docker",
        resolved_image_digest=validate_digest(trace.runtime.image_index_digest),
        platform=None,
    )


def _score_status(
    episode: NormalizedEpisode, trace: NormalizedTrace, primary_reward: str
) -> ScoreStatus:
    """Say how much weight the recorded reward carries. Spec section 7.6."""
    if not episode.ok or not trace.ok or episode.errors or trace.errors:
        return ScoreStatus.ERRORED
    if trace.reward(primary_reward) is None:
        return ScoreStatus.MISSING
    return ScoreStatus.VALID


def _evidence_status(
    trace: NormalizedTrace, evidence: EvidenceRequirements
) -> EvidenceStatus:
    """Say how complete the supporting evidence is. Spec section 7.6.

    Every artifact reference a receipt carries is a required field of the
    execution result, hashed from the bytes on the way in, so their presence is
    a property of the object rather than something to re-check. What is left to
    decide is whether the subject configuration was recorded at all and whether
    the Campaign asked for runtime evidence this release does not collect —
    absence of a Relay is not incompleteness when the Campaign says runtime
    evidence is not required.
    """
    configured = bool(trace.model_id and trace.harness_id and trace.tools)
    if configured and evidence.runtime_evidence != "required":
        return EvidenceStatus.COMPLETE
    return EvidenceStatus.PARTIAL


def _variant_artifacts(result: VariantExecutionResult) -> list[ArtifactRef]:
    """Reference the variant's evidence once, in one fixed order.

    Spec section 7.6 permits a receipt to point at the variant's artifacts
    rather than duplicating them per episode, and every one of these is a whole
    file covering the variant: the configuration the engine resolved, the raw
    upstream record, the engine's log, and the normalized projection this
    receipt was built from.
    """
    return [
        result.resolved_verifiers_config,
        result.raw_traces,
        result.eval_log,
        result.normalized_episodes,
    ]


def _receipt_id(*, run_id: str, variant: VariantName, episode_digest: Digest) -> str:
    """Return a deterministic identifier in the shape :mod:`techtree.ids` issues.

    Derived rather than random so that rebuilding a receipt from the same
    evidence produces the same identifier, which is what lets a rebuild be
    compared to what was stored.
    """
    digest = sha256_digest_bytes(
        canonical_json_bytes(
            {
                "run_id": run_id,
                "variant": variant.value,
                "episode_digest": episode_digest,
            }
        )
    )
    _, _, hexadecimal = digest.partition(":")
    return f"receipt_{hexadecimal[:_DERIVED_ID_LENGTH]}"


# ---------------------------------------------------------------------------
# One variant's receipts
# ---------------------------------------------------------------------------


def build_variant_receipts(
    *,
    run_request: RunRequest,
    variant: VariantName,
    experiment: ExperimentManifest,
    result: VariantExecutionResult,
    evaluation_backend: EvaluationBackendSpec,
    ordered_task_hashes: Sequence[Digest],
    primary_reward: str,
    evidence: EvidenceRequirements,
) -> list[EpisodeReceipt]:
    """Build exactly one receipt per committed task, in committed order.

    The join is on task hash and never on position in a file. Completion order
    varies between two concurrent variants and has nothing to do with the
    Campaign's commitment, so a receipt list built by walking the file would be
    a list nobody could pair.

    A variant with an unscored task is refused. One rollout that completed
    cleanly and produced no primary reward means scoring did not run, and a
    comparison computed over the tasks that happened to score would be a
    comparison over a taskset the Campaign never committed to.

    The lineage is settled before the episodes are looked at, so that an
    execution filed under the wrong variant is reported as the provenance
    failure it is rather than as whichever counting rule it happens to trip
    first.
    """
    _require_lineage(
        run_request=run_request,
        variant=variant,
        experiment=experiment,
        raw_artifacts=result,
        evaluation_backend=evaluation_backend,
    )
    committed = _committed_membership(ordered_task_hashes)
    episodes = _episodes_by_task(result, committed, variant)

    receipts = [
        build_episode_receipt(
            run_request=run_request,
            variant=variant,
            experiment=experiment,
            episode=episodes[task_hash],
            raw_artifacts=result,
            evaluation_backend=evaluation_backend,
            primary_reward=primary_reward,
            evidence=evidence,
        )
        for task_hash in committed
    ]
    _require_every_task_scored(receipts, primary_reward, variant)
    return receipts


def _committed_membership(ordered_task_hashes: Sequence[Digest]) -> list[Digest]:
    """Revalidate the membership a variant's receipts are ordered by."""
    committed = [validate_digest(value) for value in ordered_task_hashes]
    if not committed:
        raise VerificationError(
            "a Campaign commits to at least one task, and this one commits to "
            "none, so there is nothing to build receipts for",
            code=TASK_MEMBERSHIP_MISMATCH,
            details={"task_count": 0},
        )
    if len(set(committed)) != len(committed):
        raise VerificationError(
            "the committed membership names the same task twice, so a receipt "
            "could be attributed to either position",
            code=TASK_MEMBERSHIP_MISMATCH,
            details={"task_count": len(committed)},
        )
    return committed


def _episodes_by_task(
    result: VariantExecutionResult,
    committed: Sequence[Digest],
    variant: VariantName,
) -> dict[Digest, NormalizedEpisode]:
    """Index one variant's episodes by task, or say why they cannot be joined."""
    if len(result.episodes) != len(committed):
        raise VerificationError(
            f"the {variant.value} variant recorded {len(result.episodes)} "
            f"episodes for {len(committed)} committed tasks",
            code=EPISODE_COUNT_MISMATCH,
            details={
                "variant": variant.value,
                "recorded": len(result.episodes),
                "committed": len(committed),
            },
        )

    by_task: dict[Digest, NormalizedEpisode] = {}
    for episode in result.episodes:
        task_hash = validate_digest(episode.task_hash)
        if task_hash in by_task:
            raise VerificationError(
                f"the {variant.value} variant scored task {task_hash} twice, so "
                "one of the two results would have to be discarded",
                code=TASK_MEMBERSHIP_MISMATCH,
                details={"variant": variant.value, "task_hash": task_hash},
            )
        by_task[task_hash] = episode

    missing: list[JsonValue] = [value for value in committed if value not in by_task]
    unexpected: list[JsonValue] = [
        value for value in sorted(set(by_task) - set(committed))
    ]
    if missing or unexpected:
        raise VerificationError(
            f"the {variant.value} variant scored a different set of tasks than "
            "the Campaign commits to",
            code=TASK_MEMBERSHIP_MISMATCH,
            details={
                "variant": variant.value,
                "missing": missing,
                "unexpected": unexpected,
            },
        )
    return by_task


def _require_every_task_scored(
    receipts: Sequence[EpisodeReceipt], primary_reward: str, variant: VariantName
) -> None:
    """Refuse a variant whose clean rollouts produced no primary reward."""
    unscored: list[JsonValue] = [
        receipt.task_hash
        for receipt in receipts
        if receipt.score_status is ScoreStatus.MISSING
    ]
    if not unscored:
        return
    raise VerificationError(
        f"{len(unscored)} {variant.value} rollout(s) completed without scoring "
        f"{primary_reward!r}, which is the reward this comparison is decided on",
        code=REWARD_MISSING,
        details={
            "variant": variant.value,
            "reward": primary_reward,
            "task_hashes": unscored,
        },
    )
