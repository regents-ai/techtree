"""One resolved experiment becomes one Verifiers configuration. Spec section 6.8.

Compilation is a translation with no judgement in it. Everything the compiler
could have decided has already been decided by the Campaign and frozen into the
two experiment manifests, and this module's job is to refuse rather than to
reconcile: if a manifest and its Campaign disagree about anything at all, the
right answer is a named error, not a compiled document that splits the
difference.

Determinism is the property the rest of WP6 leans on. The same manifest, the
same run paths and the same variant always produce byte-identical TOML, which
is what lets a resolved config be compared against a compiled one and what lets
a run be reproduced from its own inputs.

The evaluation client is derived rather than chosen. Techtree emits the
credential variable the Campaign declared and omits ``base_url`` entirely, so a
Campaign that declares ``PRIME_API_KEY`` gets the pinned client's Prime
resolution (spec section 6.8's Prime profile) without Techtree writing a
provider URL into a run's inputs. There is no provider table here; which
provider a name belongs to is ``credentials``' question, not the compiler's.
"""

from __future__ import annotations

import math
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Final, NoReturn

from techtree.canonical import digest_object, sha256_digest_bytes
from techtree.errors import ValidationError
from techtree.fs import ensure_private_directory, fsync_directory, open_exclusive
from techtree.models.base import ArtifactRef, Digest
from techtree.models.campaign import (
    SUBJECT_AGENT,
    AgentSpec,
    CampaignSpec,
    VariantSchedule,
)
from techtree.models.experiment import ExperimentManifest, ExperimentVariant
from techtree.verifiers.config import (
    DockerRuntimeToml,
    EnvToml,
    EvalClientToml,
    EvalToml,
    HermesHarnessToml,
    SamplingToml,
    SubjectAgentToml,
    TasksetToml,
    TimeoutToml,
    config_to_toml_bytes,
    egress_for,
)
from techtree.verifiers.models import RunPaths, VariantExecutionPlan, VariantName

__all__ = [
    "EVAL_CONFIG_MEDIA_TYPE",
    "MANIFEST_NOT_COMPILABLE",
    "REFERENCE_HARNESS_ID",
    "compile_plans",
    "compile_variant_config",
    "divide_concurrency",
    "skill_directory_name",
    "write_variant_config",
]

#: Stable error code. Spec section 6.8.
MANIFEST_NOT_COMPILABLE: Final = "manifest_not_compilable"

#: The only subject harness WP6 executes. Spec section 6.2.
REFERENCE_HARNESS_ID: Final = "hermes-agent"

EVAL_CONFIG_MEDIA_TYPE: Final = "application/toml"

#: The minimum Campaign-wide concurrency a parallel schedule can be divided
#: from: one permit each, and no variant may be starved to zero.
_MINIMUM_PARALLEL_CONCURRENCY: Final = 2

_VARIANTS: Final[dict[ExperimentVariant, VariantName]] = {
    ExperimentVariant.BASELINE: VariantName.BASELINE,
    ExperimentVariant.CANDIDATE: VariantName.CANDIDATE,
}


def _refuse(message: str, **details: str | int | bool | None) -> NoReturn:
    """Raise the one error this module reports, with identifying details."""
    raise ValidationError(
        message,
        code=MANIFEST_NOT_COMPILABLE,
        details=dict(details),
    )


def skill_directory_name(digest: Digest) -> str:
    """Return the run-owned directory name one skill's content tree occupies.

    A skill is mounted by content, so its directory is named after its root
    digest rather than after a human-chosen label. Hermes lands each folder at
    ``<skills dir>/<folder name>``, so the folder name is part of what the
    subject sees and must therefore be a property of the skill rather than of
    whoever prepared it.
    """
    return digest.replace(":", "-", 1)


# ---------------------------------------------------------------------------
# Compilation
# ---------------------------------------------------------------------------


def compile_variant_config(
    *,
    campaign: CampaignSpec,
    experiment: ExperimentManifest,
    run_paths: RunPaths,
    variant: VariantName,
    variant_max_concurrent: int,
) -> EvalToml:
    """Translate one resolved Techtree experiment into the strict config.

    Every disagreement between the manifest and the Campaign it claims to
    derive from is refused here, before any file is written, because a
    compiled config is the last point at which the two documents can still be
    compared cheaply.
    """
    campaign_digest = digest_object(campaign)
    _check_manifest_derives_from(experiment, campaign, campaign_digest)
    _check_variant_matches(experiment, variant)

    subject = _subject_of(experiment)
    _check_subject_is_executable(subject)
    skill_paths = _resolve_skill_paths(subject, run_paths)

    output_dir = run_paths.variant_output_dir(variant)
    taskset = experiment.configuration.taskset
    allow, block = egress_for(subject.runtime.network_policy)

    # Every limit the Campaign declares, compiled into the place the engine
    # reads it. A declared budget the engine never sees is decorative, and
    # decision 0029 forbids one.
    #
    # Binding v0.1 interpretation: one Verifiers model turn is the supported
    # Hermes model-call budget unit, so ``maximum_model_calls`` compiles to
    # ``max_turns``. That mapping is VALID ONLY IF the turn-conformance check
    # holds for the pinned profile — intercepted subject generations equal
    # ``Trace.num_turns`` on every recorded canonical episode
    # (``tools/verify_turn_conformance.py``, spec section 7). If it ever
    # fails, the answer is a new ``maximum_turns`` field and
    # ``maximum_model_calls`` left unsupported, never a silent false mapping.
    #
    # ``max_total_tokens`` is derived rather than declared: a Campaign exposes
    # three publisher decisions (turns, input, output) and the total is their
    # sum (decision 0029, resolution 1).
    maximum_input = campaign.budgets.maximum_input_tokens
    maximum_output = campaign.budgets.maximum_output_tokens
    maximum_turns = campaign.budgets.maximum_model_calls
    maximum_total = (
        maximum_input + maximum_output
        if maximum_input is not None and maximum_output is not None
        else None
    )

    if variant_max_concurrent < 1:
        _refuse(
            "a variant needs at least one concurrency permit",
            variant=variant.value,
            variant_max_concurrent=variant_max_concurrent,
        )

    return EvalToml(
        model=subject.model.model_id,
        client=EvalClientToml(api_key_var=subject.model.credential_env),
        sampling=SamplingToml(
            temperature=subject.sampling.temperature,
            max_tokens=subject.sampling.max_tokens,
        ),
        env=EnvToml(
            taskset=TasksetToml(id=taskset.ref.id),
            subject=SubjectAgentToml(
                harness=HermesHarnessToml(
                    version=subject.harness.version,
                    skills=skill_paths,
                ),
                runtime=DockerRuntimeToml(
                    image=subject.runtime.image,
                    allow=allow,
                    block=block,
                    cpu=subject.runtime.cpu,
                    memory=subject.runtime.memory_gb,
                ),
                max_turns=maximum_turns,
                max_input_tokens=maximum_input,
                max_output_tokens=maximum_output,
                max_total_tokens=maximum_total,
                # The Campaign's ``timeout_seconds`` bounds ONE subject
                # rollout, not the whole variant. The variant's own bound is
                # the supervisor's hard deadline (decision 0029, layer B).
                timeout=TimeoutToml(rollout=float(campaign.execution.timeout_seconds)),
            ),
            max_concurrent_agents=1,
        ),
        num_tasks=taskset.selection.num_tasks,
        max_concurrent=variant_max_concurrent,
        output_dir=str(output_dir),
    )


def _subject_of(experiment: ExperimentManifest) -> AgentSpec:
    """Return the manifest's subject agent, or refuse."""
    subject = experiment.configuration.agents.get(SUBJECT_AGENT)
    if subject is None:
        _refuse(
            f"an experiment configuration defines a {SUBJECT_AGENT!r} agent",
            manifest_id=experiment.id,
        )
    return subject


def _check_manifest_derives_from(
    experiment: ExperimentManifest,
    campaign: CampaignSpec,
    campaign_digest: Digest,
) -> None:
    """Refuse a manifest that is not this Campaign, fully resolved."""
    if experiment.campaign_spec_digest != campaign_digest:
        _refuse(
            "the experiment manifest was derived from a different Campaign",
            manifest_id=experiment.id,
            declared=experiment.campaign_spec_digest,
            actual=campaign_digest,
        )
    if digest_object(experiment.configuration) != experiment.configuration_digest:
        _refuse(
            "the experiment configuration does not hash to its own digest",
            manifest_id=experiment.id,
        )

    configuration = experiment.configuration
    if configuration.data_policy_digest != campaign.data_policy_digest:
        _refuse(
            "the experiment and its Campaign disagree about the data policy",
            manifest_id=experiment.id,
        )
    if configuration.evaluation_backend != campaign.evaluation_backend:
        _refuse(
            "the experiment and its Campaign disagree about the evaluation backend",
            manifest_id=experiment.id,
        )
    if configuration.taskset.ref != campaign.taskset.ref:
        _refuse(
            "the experiment and its Campaign point at different tasksets",
            manifest_id=experiment.id,
        )
    if configuration.taskset.membership != campaign.taskset.membership:
        _refuse(
            "the experiment and its Campaign commit different task membership",
            manifest_id=experiment.id,
        )
    committed = len(configuration.taskset.membership.ordered_task_hashes)
    if committed != configuration.taskset.selection.num_tasks:
        _refuse(
            "the experiment commits a task count its selection does not ask for",
            manifest_id=experiment.id,
            committed=committed,
            selected=configuration.taskset.selection.num_tasks,
        )


def _check_variant_matches(
    experiment: ExperimentManifest, variant: VariantName
) -> None:
    """Refuse a manifest compiled under the other variant's name."""
    if _VARIANTS[experiment.variant] is not variant:
        _refuse(
            "the experiment manifest describes the other variant",
            manifest_id=experiment.id,
            manifest_variant=experiment.variant.value,
            requested=variant.value,
        )


def _check_subject_is_executable(subject: AgentSpec) -> None:
    """Refuse a subject WP6 has no way to run."""
    if subject.harness.id != REFERENCE_HARNESS_ID:
        _refuse(
            f"WP6 executes the {REFERENCE_HARNESS_ID!r} harness only",
            harness_id=subject.harness.id,
        )
    if subject.harness.use_bundled_skill:
        _refuse(
            "a bundled skill catalogue is an uncontrolled second difference",
            harness_id=subject.harness.id,
        )
    if subject.runtime.type != "docker":
        _refuse(
            "the subject runtime is Docker",
            runtime_type=subject.runtime.type,
        )
    if subject.trainable:
        _refuse(
            "the subject is evaluated, never trained",
            harness_id=subject.harness.id,
        )


def _resolve_skill_paths(subject: AgentSpec, run_paths: RunPaths) -> list[str]:
    """Return the run-owned directory each declared skill is mounted from."""
    paths: list[str] = []
    for skill in subject.harness.skills:
        directory = run_paths.skill_files_dir / skill_directory_name(skill.digest)
        if not run_paths.owns(directory):
            _refuse(
                "a skill must be mounted from the run's own input tree",
                path=str(directory),
            )
        paths.append(str(directory))
    return paths


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------


def write_variant_config(config: EvalToml, destination: Path) -> ArtifactRef:
    """Write deterministic TOML and return its artifact reference.

    The write is exclusive: a compiled config is an input to exactly one run,
    and silently overwriting one would make a re-read prove nothing about what
    the child was actually handed.
    """
    data = config_to_toml_bytes(config)
    ensure_private_directory(destination.parent)
    with open_exclusive(destination) as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    fsync_directory(destination.parent)
    return ArtifactRef(
        digest=sha256_digest_bytes(data),
        media_type=EVAL_CONFIG_MEDIA_TYPE,
        size=len(data),
        relative_path=None,
    )


# ---------------------------------------------------------------------------
# Planning both variants
# ---------------------------------------------------------------------------


def divide_concurrency(
    schedule: VariantSchedule, max_concurrent: int
) -> tuple[int, int]:
    """Split the Campaign-wide concurrency bound between the two variants.

    Under a sequential schedule only one variant is ever running, so each may
    use the whole declared allowance. Under a parallel schedule the bound is
    Campaign-wide (spec section 3.2) and dividing it is the executor's job:
    granting each side the full allowance would double the live subject runs
    the Campaign said it wanted.
    """
    if max_concurrent < 1:
        _refuse(
            "a Campaign declares at least one concurrency permit",
            max_concurrent=max_concurrent,
        )
    if schedule is VariantSchedule.SEQUENTIAL:
        return max_concurrent, max_concurrent
    if max_concurrent < _MINIMUM_PARALLEL_CONCURRENCY:
        _refuse(
            "a parallel schedule needs at least two concurrency permits, one "
            "for each variant",
            max_concurrent=max_concurrent,
        )
    baseline = max(1, math.floor(max_concurrent / 2))
    return baseline, max(1, max_concurrent - baseline)


def compile_plans(
    *,
    campaign: CampaignSpec,
    baseline: ExperimentManifest,
    candidate: ExperimentManifest,
    run_paths: RunPaths,
) -> tuple[VariantExecutionPlan, VariantExecutionPlan]:
    """Build both variants' plans and divide the Campaign's concurrency."""
    schedule = campaign.execution.order
    baseline_permits, candidate_permits = divide_concurrency(
        schedule, campaign.execution.max_concurrent
    )
    manifests: Mapping[VariantName, tuple[ExperimentManifest, int]] = {
        VariantName.BASELINE: (baseline, baseline_permits),
        VariantName.CANDIDATE: (candidate, candidate_permits),
    }

    plans: dict[VariantName, VariantExecutionPlan] = {}
    for variant, (manifest, permits) in manifests.items():
        config = compile_variant_config(
            campaign=campaign,
            experiment=manifest,
            run_paths=run_paths,
            variant=variant,
            variant_max_concurrent=permits,
        )
        plans[variant] = VariantExecutionPlan(
            variant=variant,
            experiment_manifest_digest=digest_object(manifest),
            experiment_manifest_path=str(run_paths.manifest_path(variant)),
            verifiers_input_config_path=str(run_paths.variant_input_config(variant)),
            verifiers_output_dir=config.output_dir,
            skill_paths=list(config.env.subject.harness.skills),
            task_count=config.num_tasks,
            max_concurrent=config.max_concurrent,
        )
    return plans[VariantName.BASELINE], plans[VariantName.CANDIDATE]
