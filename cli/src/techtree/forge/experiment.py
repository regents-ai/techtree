"""Declaring one arm of a forge experiment before it runs.

A :class:`~techtree.forge.models.ForgeRunSpec` is written from facts that are
checked here, not typed in: a repository build must have finished
qualification and every named task must be one it qualified; a Skill
collection must be accepted and still exactly what was accepted, and every
named task must be one of its members; the Hermes on the path must answer
``--version``; and a Skill, on whichever arm carries one, must scan cleanly
and carry a name Hermes would accept. What cannot be checked is not
guessed; it is listed on the specification under ``not_established``.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Final

from techtree.canonical import digest_object
from techtree.errors import PrerequisiteError, ValidationError
from techtree.forge.capture import OUTPUT_LIMITS
from techtree.forge.collection import verify_collection
from techtree.forge.docker import CONTAINER_CPUS
from techtree.forge.hermes import hermes_version
from techtree.forge.models import (
    FORGE_RUN_SPEC_SCHEMA_VERSION,
    ForgeAgentSpec,
    ForgeArm,
    ForgeBuildTasks,
    ForgeCollectionTasks,
    ForgeGradingSpec,
    ForgeInitialState,
    ForgeLimits,
    ForgeModelSpec,
    ForgeQualification,
    ForgeRunSpec,
    ForgeSamplingSpec,
    ForgeSkillSpec,
    ForgeSubjectToolset,
)
from techtree.forge.service import read_build_status
from techtree.forge.skill import scan_skill_spec
from techtree.models.base import Digest, JsonValue
from techtree.paths import TechtreePaths

__all__ = [
    "CONTAINER_MEMORY_MB",
    "NOT_ESTABLISHED",
    "SUBJECT_TOOLSETS",
    "declare_run_spec",
    "run_spec_digest",
]

#: The sandbox memory bound, in the unit Hermes' Docker backend takes. It is
#: the same 4g the forge grants its grading containers.
CONTAINER_MEMORY_MB: Final = 4096

#: The tools every subject is given: shell, files, code and Skills, each
#: routed through its sandbox.
SUBJECT_TOOLSETS: Final[tuple[ForgeSubjectToolset, ...]] = (
    "terminal",
    "file",
    "code_execution",
    "skills",
)

#: What a local experiment cannot establish and therefore says out loud.
NOT_ESTABLISHED: Final[tuple[str, ...]] = (
    "which model the provider actually served: Hermes' usage report is the "
    "only witness, and it is self-reported",
    "that the Hermes executable is unmodified: its version is what it prints",
    "the provider's sampling settings: Hermes exposes no temperature or seed, "
    "so every attempt uses the provider's default",
)


def declare_run_spec(
    paths: TechtreePaths,
    *,
    arm: ForgeArm,
    build_id: str | None = None,
    collection_id: str | None = None,
    task_ids: list[str] | None,
    skill_root: Path | None,
    provider: str,
    model_id: str,
    reasoning: str | None,
    repetitions: int,
) -> ForgeRunSpec:
    """Declare one arm of an experiment from checked facts.

    Args:
        paths: The Techtree home holding the tasks.
        arm: Which side of the comparison this is.
        build_id: A repository build that has finished qualification.
        collection_id: An accepted Skill collection; exactly one of this and
            ``build_id`` is given.
        task_ids: The tasks to run, in order; all of them when omitted.
        skill_root: The Skill's directory: required on the candidate arm,
            and on the baseline arm only when it measures an earlier Skill.
        provider: The provider name Hermes will be asked for.
        model_id: The model Hermes will be asked for.
        reasoning: Hermes' reasoning setting, when one is requested.
        repetitions: Attempts per task.

    Raises:
        PrerequisiteError: The build has not been qualified, or no ``hermes``
            is on the path.
        ValidationError: Not exactly one of a build and a collection was
            named, the build holds Skill tasks, the collection is not accepted
            as it is, a named task is not one of theirs, or the Skill does not
            fit the arm.
    """
    match (build_id, collection_id):
        case (str(), None):
            qualification = _qualification(paths, build_id)
            tasks_from: ForgeBuildTasks | ForgeCollectionTasks = ForgeBuildTasks(
                kind="build",
                build_id=build_id,
                membership_digest=qualification.membership_digest,
            )
            tasks = _subset(
                task_ids,
                qualification.qualified_task_ids,
                where="build",
                owner=build_id,
                details={"build_id": build_id},
            )
        case (None, str()):
            status = verify_collection(paths, collection_id)
            review = status.record.review
            tasks_from = ForgeCollectionTasks(
                kind="collection",
                collection_id=collection_id,
                collection_digest=status.record.collection_digest,
                version=review.version,
                membership_digest=review.membership_digest,
            )
            tasks = _subset(
                task_ids,
                [member.task_id for member in review.members],
                where="collection",
                owner=collection_id,
                details={"collection_id": collection_id},
            )
        case _:
            raise ValidationError(
                "a run is declared on exactly one build or one collection",
                code="forge_run_tasks_unnamed",
            )
    skill = _skill_for(arm, skill_root)
    executable = _hermes_executable()
    return ForgeRunSpec(
        schema_version=FORGE_RUN_SPEC_SCHEMA_VERSION,
        arm=arm,
        tasks_from=tasks_from,
        task_ids=tasks,
        grading=ForgeGradingSpec(
            procedure="harbor-compatible", executed_by="local-experiment"
        ),
        agent=ForgeAgentSpec(
            harness="hermes",
            executable=str(executable),
            version=hermes_version(executable),
        ),
        toolsets=list(SUBJECT_TOOLSETS),
        model=ForgeModelSpec(
            provider=provider,
            model_id=model_id,
            reasoning=reasoning,
            credential_source="hermes-auth-store",
        ),
        initial_state=ForgeInitialState(home="fresh-empty", memory_enabled=False),
        skill=skill,
        limits=ForgeLimits(
            agent_budget="task-timeout",
            turns="unbounded",
            container_cpus=int(CONTAINER_CPUS),
            container_memory_mb=CONTAINER_MEMORY_MB,
            network=False,
            outputs=None if isinstance(tasks_from, ForgeBuildTasks) else OUTPUT_LIMITS,
        ),
        sampling=ForgeSamplingSpec(control="provider-default", repetitions=repetitions),
        not_established=list(NOT_ESTABLISHED),
    )


def run_spec_digest(spec: ForgeRunSpec) -> Digest:
    """Return the digest that identifies a specification by its content."""
    return digest_object(spec)


def _qualification(paths: TechtreePaths, build_id: str) -> ForgeQualification:
    status = read_build_status(paths, build_id)
    if status.build is not None and status.build.source.kind == "skill":
        raise ValidationError(
            f"build {build_id} holds Skill tasks, which run only once a person "
            "has accepted them: collect and accept them with forge collect and "
            "forge accept, then run the collection with --collection",
            code="forge_source_unsupported",
            details={"build_id": build_id, "source": "skill"},
        )
    if status.qualification is None:
        raise PrerequisiteError(
            f"build {build_id} has not finished qualification, so it has no "
            "tasks an experiment can be declared on",
            code="forge_build_not_qualified",
            details={"build_id": build_id},
        )
    return status.qualification


def _subset(
    task_ids: list[str] | None,
    usable: list[str],
    *,
    where: str,
    owner: str,
    details: dict[str, JsonValue],
) -> list[str]:
    """Return the named tasks, each one of ``usable``; all of them when unnamed."""
    if task_ids is None:
        if not usable:
            raise ValidationError(
                f"{where} {owner} has no tasks that can run",
                code="forge_no_usable_tasks",
                details=details,
            )
        return list(usable)
    unusable: list[JsonValue] = [
        task_id for task_id in task_ids if task_id not in usable
    ]
    if unusable:
        raise ValidationError(
            ", ".join(str(task_id) for task_id in unusable)
            + f" {'is' if len(unusable) == 1 else 'are'} not among the tasks of "
            f"{where} {owner} that can run",
            code="forge_task_not_qualified",
            details={**details, "unqualified": unusable},
        )
    return list(task_ids)


def _skill_for(arm: ForgeArm, skill_root: Path | None) -> ForgeSkillSpec | None:
    if skill_root is None and arm is ForgeArm.BASELINE:
        return None
    if skill_root is None:
        raise ValidationError(
            "the candidate arm needs the Skill it is measuring",
            code="forge_candidate_without_skill",
        )
    spec, _ = scan_skill_spec(skill_root)
    return spec


def _hermes_executable() -> Path:
    found = shutil.which("hermes")
    if found is None:
        raise PrerequisiteError(
            "no hermes on the path; install Hermes Agent and sign in to a "
            "provider before declaring an experiment",
            code="hermes_not_found",
        )
    return Path(found)
