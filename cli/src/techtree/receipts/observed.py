"""What the engine actually resolved and ran. Spec section 7.8.

A manifest says what the experiment was supposed to be. This module says what
it turned out to be, computed from three sources that were written by something
other than Techtree:

* the traces the pinned Verifiers build recorded — which model answered, under
  which sampling settings, which harness drove it, which container it was given,
  which tools it was offered, and which rewards were scored;
* the configuration the engine resolved and wrote back out — which is where the
  skill mount paths live, and which carries its own copy of the sampling
  settings;
* what the local Docker daemon answered about the pinned subject image, asked
  once per variant immediately before that variant was launched.

Keeping them together is what makes the fingerprint an observation rather than
a restatement. The resolved configuration is the engine's own answer to "what
did you understand Techtree to be asking for", the traces are the runtime's
answer to "what did you actually do", and the daemon's answer is the only one
that can say which content was really on this machine; a disagreement between
any of them is exactly the sort of drift a controlled comparison has to detect,
so this module requires them to agree and refuses when they do not.

Three details are worth stating.

*The skill digests are recovered from the mount paths.* The normalized trace
carries the skill digests the *manifest* declared, because Verifiers records
the host directory a skill was mounted from rather than its content address. But
Techtree names that directory after the skill's root digest precisely so the
folder name is a property of the content, so the resolved configuration lets the
mounted skill be read back by digest. That reading is an observation; the
trace's copy is a declaration, and the two are required to match.

*The sampling settings are read from the rollouts, and checked against the
file.* Both are the engine's own answers, but only the rollout's copy travels
with the thing it describes. The resolved configuration's copy is required to
match it, because an engine whose file and whose rollouts disagree about how
the subject was sampled has not established either.

*Which bytes ran is a three-way agreement, not a claim.* The evaluation records
the reference it was given; the daemon says it holds that content and which
platform it served; the Campaign pins one manifest digest per platform. All
three must line up, and when they do, the digest that ran is a fact rather than
the Campaign's hope. When they do not, this module refuses — an unidentifiable
container is not a weaker result, it is no result.

Comparing this fingerprint against the declared manifest is the next slice's
work (spec section 7.9); everything here is extraction and internal
consistency.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final

from techtree.canonical import digest_object, validate_digest
from techtree.errors import ValidationError, VerificationError
from techtree.models.base import Digest, JsonValue, NonEmptyString, ProtocolModel
from techtree.models.campaign import RuntimeSpec
from techtree.verifiers.models import (
    NormalizedEpisode,
    NormalizedTrace,
    SubjectImageResolution,
)

__all__ = [
    "OBSERVED_CONFIGURATION_MISMATCH",
    "ObservedSubjectConfiguration",
    "observed_from_episodes",
    "read_resolved_config",
]

#: Stable error code. Spec section 15.
OBSERVED_CONFIGURATION_MISMATCH: Final = "observed_configuration_mismatch"

#: The directory-name spelling of a digest, which is how a mounted skill's
#: content address survives into a filesystem path.
_DIGEST_DIRECTORY_PREFIX: Final = "sha256-"


class ObservedSubjectConfiguration(ProtocolModel):
    """One normalized fingerprint of what a variant actually executed."""

    model_id: NonEmptyString
    sampling_digest: Digest
    harness_id: NonEmptyString
    harness_version: NonEmptyString
    use_bundled_skill: bool
    skill_root_digests: list[Digest]
    runtime_kind: NonEmptyString
    runtime_image: NonEmptyString
    runtime_image_index_digest: Digest
    runtime_platform: NonEmptyString
    runtime_image_platform_digest: Digest
    tool_inventory_digest: Digest
    reward_contract_digest: Digest
    verifiers_version: NonEmptyString
    verifiers_revision: NonEmptyString


def read_resolved_config(path: Path) -> dict[str, Any]:
    """Read the configuration the engine resolved and wrote back out.

    JSON, because that is what the engine writes: it dumps the resolved model
    whole, nulls included, so an explicitly-unset setting round-trips as itself
    (``docs/verifiers-pin-0.3.1.md``, deviation D1). TOML could not carry those
    nulls, which is why upstream stopped using it here.
    """
    try:
        document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError(
            "the configuration this variant's engine resolved could not be "
            "read, so what it actually ran cannot be established",
            code=OBSERVED_CONFIGURATION_MISMATCH,
            details={"path": str(path)},
        ) from error
    return document


def observed_from_episodes(
    episodes: Sequence[NormalizedEpisode],
    *,
    resolved_config: Mapping[str, Any],
    image_resolution: SubjectImageResolution,
    runtime: RuntimeSpec,
) -> ObservedSubjectConfiguration:
    """Fingerprint one variant, requiring every episode to agree.

    Spec section 7.8 names this ``observed_from_receipts``. It takes the
    normalized episodes instead, because the frozen
    :class:`~techtree.models.episode_receipt.EpisodeReceipt` carries a
    reward-and-lineage record rather than a configuration record: it does not
    hold the model, the harness, the tool inventory or the sampling parameters,
    and reading those off it is not possible. The episodes are the evidence the
    receipts were built from, so the fingerprint and the receipts describe the
    same execution.
    """
    traces = [trace for episode in episodes for trace in episode.traces]
    if not traces:
        raise VerificationError(
            "this variant recorded no subject trace, so there is no observed "
            "configuration to establish",
            code=OBSERVED_CONFIGURATION_MISMATCH,
            details={"episodes": len(episodes)},
        )

    reference = traces[0]
    _require_no_drift(traces)

    mounted = _mounted_skill_digests(resolved_config)
    declared = [validate_digest(value) for value in reference.skill_root_digests]
    if mounted != declared:
        raise VerificationError(
            "the skills the engine mounted are not the skills this variant's "
            "traces record, so what the subject was given is not what the "
            "experiment declared",
            code=OBSERVED_CONFIGURATION_MISMATCH,
            details={
                "mounted": _digest_detail(mounted),
                "recorded": _digest_detail(declared),
            },
        )
    _require_config_agrees_with_traces(reference, resolved_config)
    platform_digest = _resolved_platform_digest(reference, image_resolution, runtime)

    return ObservedSubjectConfiguration(
        model_id=reference.model_id,
        sampling_digest=digest_object(reference.sampling),
        harness_id=reference.harness_id,
        harness_version=reference.harness_version,
        use_bundled_skill=reference.use_bundled_skill,
        skill_root_digests=mounted,
        runtime_kind=reference.runtime.kind,
        runtime_image=reference.runtime.image,
        runtime_image_index_digest=image_resolution.index_digest,
        runtime_platform=image_resolution.platform,
        runtime_image_platform_digest=platform_digest,
        tool_inventory_digest=digest_object(
            [
                {
                    "name": tool.name,
                    "description_digest": tool.description_digest,
                    "parameters_digest": tool.parameters_digest,
                }
                for tool in sorted(reference.tools, key=lambda tool: tool.name)
            ]
        ),
        reward_contract_digest=digest_object(
            [
                {"name": reward.name, "weight": reward.weight}
                for reward in sorted(reference.rewards, key=lambda item: item.name)
            ]
        ),
        verifiers_version=reference.verifiers_version,
        verifiers_revision=reference.verifiers_revision,
    )


# ---------------------------------------------------------------------------
# Agreement
# ---------------------------------------------------------------------------


def _require_no_drift(traces: Sequence[NormalizedTrace]) -> None:
    """Reject a variant whose own traces describe two different subjects.

    Every rollout of one variant is one configuration executed many times. Two
    rollouts that disagree about the model, the harness, the container or the
    tools were not the same experiment, and averaging their rewards would
    average two experiments.
    """
    for label, observed in (
        ("model", {trace.model_id for trace in traces}),
        ("harness", {trace.harness_id for trace in traces}),
        ("harness version", {trace.harness_version for trace in traces}),
        ("bundled-skill setting", {trace.use_bundled_skill for trace in traces}),
        ("sampling", {digest_object(trace.sampling) for trace in traces}),
        ("runtime kind", {trace.runtime.kind for trace in traces}),
        ("runtime image", {trace.runtime.image for trace in traces}),
        (
            "runtime image digest",
            {trace.runtime.image_index_digest for trace in traces},
        ),
        (
            "skill list",
            {tuple(trace.skill_root_digests) for trace in traces},
        ),
        (
            "tool inventory",
            {tuple(sorted(tool.name for tool in trace.tools)) for trace in traces},
        ),
        (
            "reward contract",
            {
                tuple(sorted((reward.name, reward.weight) for reward in trace.rewards))
                for trace in traces
            },
        ),
        (
            "Verifiers build",
            {(trace.verifiers_version, trace.verifiers_revision) for trace in traces},
        ),
    ):
        if len(observed) > 1:
            raise VerificationError(
                f"this variant's rollouts do not agree on the {label} they ran, "
                "so they are not one configuration measured many times",
                code=OBSERVED_CONFIGURATION_MISMATCH,
                details={
                    "field": label,
                    "observed": _text_detail(observed),
                },
            )


def _require_config_agrees_with_traces(
    trace: NormalizedTrace, resolved_config: Mapping[str, Any]
) -> None:
    """Require the engine's resolution and the runtime's record to agree."""
    subject = _subject_of(resolved_config)
    harness = _table(subject, "harness")
    runtime = _table(subject, "runtime")

    for label, resolved, recorded in (
        ("model", resolved_config.get("model"), trace.model_id),
        ("harness", harness.get("id"), trace.harness_id),
        ("harness version", harness.get("version"), trace.harness_version),
        ("runtime kind", runtime.get("type"), trace.runtime.kind),
        ("runtime image", runtime.get("image"), trace.runtime.image),
        (
            "bundled-skill setting",
            harness.get("use_bundled_skill"),
            trace.use_bundled_skill,
        ),
    ):
        if resolved == recorded:
            continue
        raise VerificationError(
            f"the engine resolved a different {label} than this variant's "
            "traces record",
            code=OBSERVED_CONFIGURATION_MISMATCH,
            details={
                "field": label,
                "resolved": str(resolved),
                "recorded": str(recorded),
            },
        )

    if _sampling_of(resolved_config) != dict(trace.sampling):
        raise VerificationError(
            "the sampling settings the engine resolved are not the ones this "
            "variant's rollouts record being sampled under",
            code=OBSERVED_CONFIGURATION_MISMATCH,
            details={
                "resolved": _text_detail(_sampling_of(resolved_config)),
                "recorded": _text_detail(trace.sampling),
            },
        )


def _resolved_platform_digest(
    trace: NormalizedTrace,
    image_resolution: SubjectImageResolution,
    runtime: RuntimeSpec,
) -> Digest:
    """Return the image digest that actually ran, and refuse if it is unclear.

    Three separate statements have to line up before the phrase "this container
    ran" means anything. The evaluation says which reference it was given. The
    local daemon says it holds that reference's content, and which platform it
    resolved the reference to on this host. The Campaign says which manifest
    that platform pins. Any disagreement leaves what ran unidentified, which is
    a refusal rather than a weaker claim.
    """
    if image_resolution.image != trace.runtime.image:
        raise VerificationError(
            "the image the daemon was asked about is not the image this "
            "variant's rollouts ran",
            code=OBSERVED_CONFIGURATION_MISMATCH,
            details={
                "resolved": image_resolution.image,
                "recorded": trace.runtime.image,
            },
        )
    if image_resolution.index_digest != trace.runtime.image_index_digest:
        raise VerificationError(
            "the content the daemon holds for the subject image is not the "
            "content this variant's rollouts name",
            code=OBSERVED_CONFIGURATION_MISMATCH,
            details={
                "resolved": image_resolution.index_digest,
                "recorded": trace.runtime.image_index_digest,
            },
        )
    if image_resolution.index_digest != runtime.image_index_digest:
        raise VerificationError(
            "the content the daemon holds for the subject image is not the "
            "content the Campaign pinned",
            code=OBSERVED_CONFIGURATION_MISMATCH,
            details={
                "resolved": image_resolution.index_digest,
                "pinned": runtime.image_index_digest,
            },
        )
    pinned = runtime.image_platform_digests.get(image_resolution.platform)
    if pinned is None:
        raise VerificationError(
            "the daemon served the subject image on a platform the Campaign "
            "pins no manifest for, so which bytes ran cannot be established",
            code=OBSERVED_CONFIGURATION_MISMATCH,
            details={
                "platform": image_resolution.platform,
                "pinned_platforms": _text_detail(runtime.image_platform_digests),
            },
        )
    return validate_digest(pinned)


# ---------------------------------------------------------------------------
# Reading the resolved configuration
# ---------------------------------------------------------------------------


def _subject_of(resolved_config: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return the resolved subject seat, or refuse a configuration without one."""
    environment = _table(resolved_config, "env")
    subject = environment.get("subject")
    if not isinstance(subject, Mapping):
        raise VerificationError(
            "the configuration the engine resolved declares no subject seat, so "
            "it does not describe an evaluation of a subject",
            code=OBSERVED_CONFIGURATION_MISMATCH,
            details={"tables": _text_detail(resolved_config)},
        )
    return subject


def _table(document: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    """Return one required table of a resolved configuration."""
    value = document.get(name)
    if not isinstance(value, Mapping):
        raise VerificationError(
            f"the configuration the engine resolved has no {name!r} table, so "
            "what it ran cannot be established",
            code=OBSERVED_CONFIGURATION_MISMATCH,
            details={"table": name},
        )
    return value


def _sampling_of(resolved_config: Mapping[str, Any]) -> dict[str, JsonValue]:
    """Return the sampling parameters the engine wrote back out."""
    sampling = _table(resolved_config, "sampling")
    values: dict[str, JsonValue] = {}
    for key, value in sorted(sampling.items()):
        if not isinstance(value, str | int | float | bool) and value is not None:
            raise VerificationError(
                "the resolved sampling parameters hold a value that is not a "
                "scalar, so they cannot be fingerprinted",
                code=OBSERVED_CONFIGURATION_MISMATCH,
                details={"key": str(key)},
            )
        values[str(key)] = value
    if not values:
        raise VerificationError(
            "the configuration the engine resolved records no sampling "
            "parameters, so how the subject was sampled is unknown",
            code=OBSERVED_CONFIGURATION_MISMATCH,
            details={},
        )
    return values


def _mounted_skill_digests(resolved_config: Mapping[str, Any]) -> list[Digest]:
    """Recover the content address of every skill the engine mounted."""
    harness = _table(_subject_of(resolved_config), "harness")
    mounted = harness.get("skills", [])
    if not isinstance(mounted, list):
        raise VerificationError(
            "the resolved harness does not list the skills it mounted",
            code=OBSERVED_CONFIGURATION_MISMATCH,
            details={},
        )

    digests: list[Digest] = []
    for entry in mounted:
        name = Path(str(entry)).name
        if not name.startswith(_DIGEST_DIRECTORY_PREFIX):
            raise VerificationError(
                "the engine mounted a skill from a directory that is not named "
                "after the skill's content, so what the subject read cannot be "
                "identified",
                code=OBSERVED_CONFIGURATION_MISMATCH,
                details={"directory": name},
            )
        digests.append(validate_digest(name.replace("-", ":", 1)))
    return digests


def _digest_detail(digests: Sequence[Digest]) -> list[JsonValue]:
    """Return a digest list in the shape typed error details carry."""
    return [value for value in digests]


def _text_detail(values: Iterable[object]) -> list[JsonValue]:
    """Return an ordered, printable list in the shape error details carry."""
    return [text for text in sorted(str(value) for value in values)]
