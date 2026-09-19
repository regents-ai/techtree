"""Declaring one arm of a forge experiment before it runs.

A :class:`~techtree.forge.models.ForgeRunSpec` is written from facts that are
checked here, not typed in: the build must have finished qualification, every
named task must be one it qualified, the Hermes on the path must answer
``--version``, and a candidate Skill must scan cleanly and carry a name Hermes
would accept. What cannot be checked is not guessed; it is listed on the
specification under ``not_established``.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Final

from techtree.canonical import digest_object
from techtree.errors import PrerequisiteError, ValidationError
from techtree.forge.docker import CONTAINER_CPUS
from techtree.forge.models import (
    FORGE_RUN_SPEC_SCHEMA_VERSION,
    ForgeAgentSpec,
    ForgeArm,
    ForgeGradingSpec,
    ForgeInitialState,
    ForgeLimits,
    ForgeModelSpec,
    ForgeQualification,
    ForgeRunSpec,
    ForgeSamplingSpec,
    ForgeSkillSpec,
)
from techtree.forge.process import run_command
from techtree.forge.service import read_build_status
from techtree.forge.skill import scan_skill_spec
from techtree.models.base import Digest, JsonValue
from techtree.paths import TechtreePaths

__all__ = [
    "CONTAINER_MEMORY_MB",
    "NOT_ESTABLISHED",
    "declare_run_spec",
    "hermes_version",
    "run_spec_digest",
]

#: The sandbox memory bound, in the unit Hermes' Docker backend takes. It is
#: the same 4g the forge grants its grading containers.
CONTAINER_MEMORY_MB: Final = 4096
#: The Hermes version banner: ``Hermes Agent v0.21.3 (2026.9.14) · upstream …``.
_VERSION_BANNER: Final = re.compile(r"^Hermes Agent v(?P<version>\S+)")
_VERSION_TIMEOUT_SECONDS: Final = 30.0

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
    build_id: str,
    task_ids: list[str] | None,
    skill_root: Path | None,
    provider: str,
    model_id: str,
    reasoning: str | None,
    repetitions: int,
) -> ForgeRunSpec:
    """Declare one arm of an experiment from checked facts.

    Args:
        paths: The Techtree home holding the build.
        arm: Which side of the comparison this is.
        build_id: A build that has finished qualification.
        task_ids: The qualified tasks to run, in order; all of them when omitted.
        skill_root: The candidate Skill's directory; required on the candidate
            arm and refused on the baseline arm.
        provider: The provider name Hermes will be asked for.
        model_id: The model Hermes will be asked for.
        reasoning: Hermes' reasoning setting, when one is requested.
        repetitions: Attempts per task.

    Raises:
        PrerequisiteError: The build has not been qualified, or no ``hermes``
            is on the path.
        ValidationError: A named task was not qualified, or the Skill does
            not fit the arm.
    """
    qualification = _qualification(paths, build_id)
    tasks = _qualified_subset(qualification, task_ids)
    skill = _skill_for(arm, skill_root)
    executable = _hermes_executable()
    return ForgeRunSpec(
        schema_version=FORGE_RUN_SPEC_SCHEMA_VERSION,
        arm=arm,
        build_id=build_id,
        membership_digest=qualification.membership_digest,
        task_ids=tasks,
        grading=ForgeGradingSpec(
            procedure="harbor-compatible", executed_by="local-experiment"
        ),
        agent=ForgeAgentSpec(
            harness="hermes",
            executable=str(executable),
            version=hermes_version(executable),
        ),
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
        ),
        sampling=ForgeSamplingSpec(control="provider-default", repetitions=repetitions),
        not_established=list(NOT_ESTABLISHED),
    )


def run_spec_digest(spec: ForgeRunSpec) -> Digest:
    """Return the digest that identifies a specification by its content."""
    return digest_object(spec)


def _qualification(paths: TechtreePaths, build_id: str) -> ForgeQualification:
    status = read_build_status(paths, build_id)
    if status.qualification is None:
        raise PrerequisiteError(
            f"build {build_id} has not finished qualification, so it has no "
            "tasks an experiment can be declared on",
            code="forge_build_not_qualified",
            details={"build_id": build_id},
        )
    return status.qualification


def _qualified_subset(
    qualification: ForgeQualification, task_ids: list[str] | None
) -> list[str]:
    qualified = qualification.qualified_task_ids
    if task_ids is None:
        if not qualified:
            raise ValidationError(
                f"build {qualification.build_id} qualified no tasks",
                code="forge_no_usable_tasks",
                details={"build_id": qualification.build_id},
            )
        return list(qualified)
    unqualified: list[JsonValue] = [
        task_id for task_id in task_ids if task_id not in qualified
    ]
    if unqualified:
        raise ValidationError(
            "only a task the build qualified can be run: "
            + ", ".join(str(task_id) for task_id in unqualified),
            code="forge_task_not_qualified",
            details={
                "build_id": qualification.build_id,
                "unqualified": unqualified,
                "qualified": [task_id for task_id in qualified],
            },
        )
    return list(task_ids)


def _skill_for(arm: ForgeArm, skill_root: Path | None) -> ForgeSkillSpec | None:
    if arm is ForgeArm.BASELINE:
        if skill_root is not None:
            raise ValidationError(
                "the baseline arm runs without a Skill; name the Skill on the "
                "candidate arm only",
                code="forge_baseline_with_skill",
                details={"skill_root": str(skill_root)},
            )
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


def hermes_version(executable: Path) -> str:
    """Return the version the Hermes at ``executable`` prints for itself."""
    completed = run_command([str(executable), "--version"], _VERSION_TIMEOUT_SECONDS)
    first_line = completed.stdout.splitlines()[0] if completed.stdout else ""
    match = _VERSION_BANNER.match(first_line)
    if completed.returncode != 0 or match is None:
        raise PrerequisiteError(
            f"{executable} did not report a Hermes Agent version",
            code="hermes_version_unreadable",
            details={
                "executable": str(executable),
                "exit_code": completed.returncode,
                "first_line": first_line,
            },
        )
    return match.group("version")
