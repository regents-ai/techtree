"""One revision of a measured forge Skill: prepared, screened, measured, kept.

A revision is the forge's half of ``uplift prepare`` and ``uplift start``. It
starts from a finished comparison, takes one revised Skill a person names,
and declares the run that measures it: the candidate run's own specification
with the Skill alone replaced, so the comparability gate holds the new arm to
the same baseline by construction rather than by promise. The Hermes the
specification names is asked for its version again, and a different answer
is a refusal, because the run would otherwise claim an agent it did not use.

Before anything runs the revised Skill is screened against what a repository
task hides: the reference patch, the tests, and the tests' names. Screening
is evidence-based and recorded, not a refusal — a Skill may legitimately name
the function it repairs — so every line the Skill shares with that material
is written on the revision for the person who approves the run to see, and
the run's report carries it.

Measuring runs the new arm and compares it against the same baseline the
parent was compared against. The revision then names its run, its comparison
and a one-line verdict against the comparison it revised from, and is kept
whether it improved or regressed. Nothing here proposes, chooses or loops.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Literal

from pydantic import ValidationError as ModelValidationError

from techtree.canonical import canonical_json_bytes
from techtree.errors import NotFoundError, PrerequisiteError, ValidationError
from techtree.forge.comparability import (
    assert_comparable_run_specs,
    compare_run_specs,
)
from techtree.forge.compare import compare_runs, read_comparison_status
from techtree.forge.experiment import run_spec_digest
from techtree.forge.hermes import hermes_version
from techtree.forge.models import (
    FORGE_REVISION_SCHEMA_VERSION,
    ForgeComparisonRecord,
    ForgeComparisonStatus,
    ForgeRevisionRecord,
    ForgeRevisionStatus,
    ForgeRunSpec,
    ForgeRunStatus,
    ForgeScreeningFinding,
)
from techtree.forge.qualify import read_task_facts
from techtree.forge.run import ForgeRunner, read_run_status
from techtree.forge.service import read_build_status
from techtree.forge.skill import SKILL_DIRNAME, scan_skill_spec, snapshot_skill
from techtree.fs import atomic_write_bytes, atomic_write_json
from techtree.ids import new_id, validate_id
from techtree.paths import TechtreePaths
from techtree.presentation.sanitize import sanitize_label

__all__ = [
    "REVISION_FILENAME",
    "SPEC_FILENAME",
    "MeasuredRevision",
    "measure_revision",
    "prepare_revision",
    "read_revision_status",
    "screen_skill",
]

REVISION_FILENAME: Final = "revision.json"
SPEC_FILENAME: Final = "spec.json"
#: A line shorter than this is too ordinary to be evidence of copying:
#: ``import pytest`` and ``return self`` occur in any Python file.
_MINIMUM_LINE: Final = 24
_EXCERPT_LIMIT: Final = 120
#: A verdict is one sentence naming two Skills; it is never cut short.
_VERDICT_LIMIT: Final = 400


def prepare_revision(
    paths: TechtreePaths,
    *,
    comparison_id: str,
    skill_root: Path,
    label: str | None,
) -> ForgeRevisionStatus:
    """Declare and screen one revised Skill against a finished comparison."""
    comparison = read_comparison_status(paths, comparison_id).record
    parent = read_run_status(paths, comparison.candidate_run_id)
    baseline = read_run_status(paths, comparison.baseline_run_id)
    if parent.spec.skill is None:
        raise ValidationError(
            "the candidate run carries no Skill, so there is nothing to revise",
            code="forge_candidate_without_skill",
            details={"comparison_id": comparison_id},
        )
    try:
        skill, files = scan_skill_spec(skill_root, name=label)
    except ModelValidationError as error:
        raise ValidationError(
            "the label is not a name Hermes accepts for a Skill: lowercase "
            "letters, digits, dashes and underscores, starting with a letter",
            code="forge_skill_name_invalid",
            details={"label": label or ""},
        ) from error
    if skill.root_digest == parent.spec.skill.root_digest:
        raise ValidationError(
            "the revised Skill is the Skill the comparison measured; a "
            "revision has to differ from it",
            code="forge_revision_unchanged",
            details={"skill": skill.root_digest},
        )
    executable = Path(parent.spec.agent.executable)
    found = hermes_version(executable)
    if found != parent.spec.agent.version:
        raise PrerequisiteError(
            f"{executable} now reports Hermes Agent v{found}, not the "
            f"v{parent.spec.agent.version} the comparison was made with, so a "
            "revision measured with it would not be the same experiment",
            code="forge_agent_changed",
            details={"declared": parent.spec.agent.version, "found": found},
        )

    spec = parent.spec.model_copy(update={"skill": skill})
    comparability = compare_run_specs(baseline.spec, spec)
    assert_comparable_run_specs(comparability)
    build_id = spec.require_build("Repository Skill screening").build_id
    screening = screen_skill(
        paths, build_id=build_id, task_ids=spec.task_ids, files=files
    )

    revision_id = new_id("forgerev")
    directory = paths.forge_revision_dir(revision_id)
    directory.mkdir(parents=True, mode=0o700)
    snapshot_skill(files, directory / SKILL_DIRNAME)
    atomic_write_bytes(directory / SPEC_FILENAME, canonical_json_bytes(spec))
    now = datetime.now(UTC)
    record = ForgeRevisionRecord(
        schema_version=FORGE_REVISION_SCHEMA_VERSION,
        revision_id=revision_id,
        created_at=now,
        updated_at=now,
        comparison_id=comparison.comparison_id,
        build_id=build_id,
        baseline_run_id=comparison.baseline_run_id,
        parent_run_id=comparison.candidate_run_id,
        parent_skill_digest=parent.spec.skill.root_digest,
        skill=skill,
        spec_digest=run_spec_digest(spec),
        comparability=comparability,
        screening=screening,
        state="prepared",
        measured_run_id=None,
        measured_comparison_id=None,
        verdict=None,
    )
    atomic_write_json(directory / REVISION_FILENAME, record.model_dump(mode="json"))
    return ForgeRevisionStatus(
        revision_id=revision_id, path=str(directory), spec=spec, record=record
    )


@dataclass(frozen=True)
class MeasuredRevision:
    """What measuring left: the revision as updated, its run, its comparison."""

    revision: ForgeRevisionStatus
    run: ForgeRunStatus
    comparison: ForgeComparisonStatus


def measure_revision(
    paths: TechtreePaths, revision_id: str, runner: ForgeRunner
) -> MeasuredRevision:
    """Run the revision's arm, compare it with the baseline, and record both."""
    status = read_revision_status(paths, revision_id)
    record = status.record
    if record.state != "prepared":
        raise ValidationError(
            f"revision {revision_id} was already measured as run "
            f"{record.measured_run_id}; prepare a new revision to measure again",
            code="forge_revision_measured",
            details={
                "revision_id": revision_id,
                "measured_run_id": record.measured_run_id or "",
            },
        )
    run = runner.run(status.spec, Path(status.path) / SKILL_DIRNAME)
    comparison = compare_runs(paths, record.baseline_run_id, run.run_id)
    parent = read_comparison_status(paths, record.comparison_id).record
    measured = record.model_copy(
        update={
            "updated_at": datetime.now(UTC),
            "state": "measured",
            "measured_run_id": run.run_id,
            "measured_comparison_id": comparison.comparison_id,
            "verdict": _verdict(parent, comparison.record),
        }
    )
    atomic_write_json(
        Path(status.path) / REVISION_FILENAME, measured.model_dump(mode="json")
    )
    return MeasuredRevision(
        revision=status.model_copy(update={"record": measured}),
        run=run,
        comparison=comparison,
    )


def read_revision_status(paths: TechtreePaths, revision_id: str) -> ForgeRevisionStatus:
    """Read one revision's specification and record back from its directory."""
    directory = paths.forge_revision_dir(validate_id(revision_id, "forgerev"))
    spec_file = directory / SPEC_FILENAME
    record_file = directory / REVISION_FILENAME
    if not spec_file.is_file() or not record_file.is_file():
        raise NotFoundError(
            f"no recorded forge revision {revision_id}",
            code="forge_revision_not_found",
            details={"revision_id": revision_id, "path": str(directory)},
        )
    try:
        spec = ForgeRunSpec.model_validate_json(spec_file.read_bytes())
        record = ForgeRevisionRecord.model_validate_json(record_file.read_bytes())
    except ModelValidationError as error:
        issue = error.errors(include_input=False, include_url=False)[0]
        raise ValidationError(
            f"invalid forge revision evidence: {issue['msg']}",
            code="forge_evidence_invalid",
            details={"revision_id": revision_id, "path": str(directory)},
        ) from error
    return ForgeRevisionStatus(
        revision_id=revision_id, path=str(directory), spec=spec, record=record
    )


# ---------------------------------------------------------------------------
# Screening
# ---------------------------------------------------------------------------


def screen_skill(
    paths: TechtreePaths,
    *,
    build_id: str,
    task_ids: list[str],
    files: list[tuple[Path, str]],
) -> list[ForgeScreeningFinding]:
    """Record every Skill line that also occurs in a task's hidden material.

    Three kinds of material are read per task: the added lines of the
    reference patch, every line of every file under ``tests``, and the test
    names the task grades by. A Skill line is compared after stripping, and
    only when it is long enough to be more than coincidence.
    """
    build = read_build_status(paths, build_id).build
    if build is None:
        raise ValidationError(
            f"build {build_id} has no build record for repository screening",
            code="forge_build_not_qualified",
            details={"build_id": build_id},
        )
    build.require_repository_source("Repository Skill screening")
    skill_lines = [
        (relative, number, line)
        for source, relative in files
        for number, line in _text_lines(source)
    ]
    findings: list[ForgeScreeningFinding] = []
    for task_id in task_ids:
        task_dir = paths.forge_build_dir(build_id) / "tasks" / task_id
        patch = {
            line[1:].strip()
            for _, line in _text_lines(task_dir / "solution" / "patch.diff")
            if line.startswith("+") and not line.startswith("+++")
        }
        tests = {
            line.strip()
            for path in sorted(
                p for p in (task_dir / "tests").rglob("*") if p.is_file()
            )
            for _, line in _text_lines(path)
        }
        facts = read_task_facts(task_dir)
        names = {
            _test_name(test_id)
            for test_id in (*facts.fail_to_pass, *facts.pass_to_pass)
        }
        materials: list[tuple[Literal["reference_patch", "tests"], set[str]]] = [
            ("reference_patch", patch),
            ("tests", tests),
        ]
        for relative, number, line in skill_lines:
            stripped = line.strip()
            if len(stripped) < _MINIMUM_LINE:
                continue
            for material, haystack in materials:
                if stripped in haystack:
                    findings.append(
                        ForgeScreeningFinding(
                            task_id=task_id,
                            material=material,
                            skill_path=relative,
                            line=number,
                            excerpt=sanitize_label(stripped, maximum=_EXCERPT_LIMIT),
                        )
                    )
            if any(name in stripped for name in names if name):
                findings.append(
                    ForgeScreeningFinding(
                        task_id=task_id,
                        material="test_names",
                        skill_path=relative,
                        line=number,
                        excerpt=sanitize_label(stripped, maximum=_EXCERPT_LIMIT),
                    )
                )
    return findings


def _text_lines(path: Path) -> list[tuple[int, str]]:
    """Return a file's lines numbered from one, or nothing for non-text."""
    try:
        text = path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    return list(enumerate(text.splitlines(), start=1))


def _test_name(test_id: str) -> str:
    """Return the function name of a pytest node id, without its parameters."""
    _, _, name = test_id.rpartition("::")
    return name.partition("[")[0]


# ---------------------------------------------------------------------------
# The verdict
# ---------------------------------------------------------------------------


def _verdict(parent: ForgeComparisonRecord, revised: ForgeComparisonRecord) -> str:
    """Say, in one sentence, how the revision did against the Skill it revised."""
    before = parent.candidate.mean_reward
    after = revised.candidate.mean_reward
    partial = "" if parent.complete and revised.complete else " Partial evidence:"
    if before is None or after is None:
        return sanitize_label(
            f"{partial} the revision could not be placed against the Skill it "
            "revised, because one of the two has no graded pair.".strip(),
            maximum=_VERDICT_LIMIT,
        )
    change = after - before
    word = (
        "improved on" if change > 0 else "regressed from" if change < 0 else "matched"
    )
    return sanitize_label(
        f"{partial} Against the same baseline, {revised.skill_name} {word} "
        f"{parent.skill_name}: mean reward {after:.2f} against {before:.2f} "
        f"({change:+.2f}); {revised.wins} won, {revised.losses} lost, "
        f"{revised.ties} tied of {revised.pairs_planned}. Kept as measured.".strip(),
        maximum=_VERDICT_LIMIT,
    )
