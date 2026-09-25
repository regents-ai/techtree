"""One revision of a measured forge Skill: prepared, screened, measured, kept.

A revision is the forge's half of ``uplift prepare`` and ``uplift start``. It
starts from a finished comparison, takes one revised Skill a person names,
and declares the run that measures it: the candidate run's own specification
with the Skill alone replaced, so the comparability gate holds the new arm to
the same baseline by construction rather than by promise. The Hermes the
specification names is asked for its version again, and a different answer
is a refusal, because the run would otherwise claim an agent it did not use.

Before anything runs the revised Skill is screened against what a task
hides from the agent: for a repository task the reference patch, the tests,
and the tests' names; for a task written from a Skill its reference
solutions and its tests, and for a held-out task of a collection also its
instruction and its inputs, which the agent that wrote the revision never
saw. Screening is evidence-based and recorded, not a refusal — a Skill may
legitimately name the function it repairs — so every line the Skill shares
with that material is written on the revision for the person who approves
the run to see, and the run's report carries it.

Measuring runs the new arm on every task and compares it against the same
baseline the parent was compared against. The revision then names its run,
its comparison and a one-line verdict against the comparison it revised
from, and is kept whether it improved or regressed. On a collection that
verdict is computed on the held-out tasks alone (founder decision 2a), so a
Skill that memorised the tasks it studied cannot pass for an improvement;
how it did on the tasks it could see is recorded beside it, labelled as
such. Nothing here proposes, chooses or loops.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Literal, NamedTuple

from pydantic import ValidationError as ModelValidationError

from techtree.canonical import canonical_json_bytes
from techtree.errors import NotFoundError, PrerequisiteError, ValidationError
from techtree.forge.collection import read_collection_status
from techtree.forge.comparability import (
    assert_comparable_run_specs,
    compare_run_specs,
)
from techtree.forge.compare import compare_runs, read_comparison_status
from techtree.forge.experiment import run_spec_digest
from techtree.forge.hermes import hermes_version
from techtree.forge.models import (
    FORGE_REVISION_SCHEMA_VERSION,
    ForgeBuildTasks,
    ForgeCollectionTasks,
    ForgeComparisonRecord,
    ForgeComparisonStatus,
    ForgePartSummary,
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
    screening = screen_skill(
        paths, tasks_from=spec.tasks_from, task_ids=spec.task_ids, files=files
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
        tasks_from=spec.tasks_from,
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
        study_verdict=None,
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
    verdict, study_verdict = _verdicts(parent, comparison.record)
    measured = record.model_copy(
        update={
            "updated_at": datetime.now(UTC),
            "state": "measured",
            "measured_run_id": run.run_id,
            "measured_comparison_id": comparison.comparison_id,
            "verdict": verdict,
            "study_verdict": study_verdict,
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


_Material = Literal[
    "reference_patch", "reference_solution", "tests", "instruction", "inputs"
]


def screen_skill(
    paths: TechtreePaths,
    *,
    tasks_from: ForgeBuildTasks | ForgeCollectionTasks,
    task_ids: list[str],
    files: list[tuple[Path, str]],
) -> list[ForgeScreeningFinding]:
    """Record every Skill line that also occurs in a task's hidden material.

    A repository task hides three kinds of material: the added lines of the
    reference patch, every line of every file under ``tests``, and the test
    names the task grades by. A task written from a Skill hides every line
    of every file under ``solution`` and under ``tests``; a held-out task of
    a collection also hides every line of its ``instruction.md`` and of its
    inputs, the files under ``environment`` other than the ``Dockerfile``
    that only builds its image. A Skill line is compared after stripping,
    and only when it is long enough to be more than coincidence.
    """
    skill_lines = [
        (relative, number, line)
        for source, relative in files
        for number, line in _text_lines(source)
    ]
    findings: list[ForgeScreeningFinding] = []
    for task_id, materials, names in _hidden_material(paths, tasks_from, task_ids):
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


def _hidden_material(
    paths: TechtreePaths,
    tasks_from: ForgeBuildTasks | ForgeCollectionTasks,
    task_ids: list[str],
) -> list[tuple[str, list[tuple[_Material, set[str]]], set[str]]]:
    """Return, per task, the hidden lines by kind and the test names it grades by."""
    match tasks_from:
        case ForgeBuildTasks(build_id=build_id):
            build = read_build_status(paths, build_id).build
            if build is None:
                raise ValidationError(
                    f"build {build_id} has no build record for repository screening",
                    code="forge_build_not_qualified",
                    details={"build_id": build_id},
                )
            build.require_repository_source("Repository Skill screening")
            hidden = []
            for task_id in task_ids:
                task_dir = paths.forge_build_dir(build_id) / "tasks" / task_id
                patch = {
                    line[1:].strip()
                    for _, line in _text_lines(task_dir / "solution" / "patch.diff")
                    if line.startswith("+") and not line.startswith("+++")
                }
                facts = read_task_facts(task_dir)
                names = {
                    _test_name(test_id)
                    for test_id in (*facts.fail_to_pass, *facts.pass_to_pass)
                }
                materials: list[tuple[_Material, set[str]]] = [
                    ("reference_patch", patch),
                    ("tests", _lines_under(task_dir / "tests")),
                ]
                hidden.append((task_id, materials, names))
            return hidden
        case ForgeCollectionTasks(collection_id=collection_id):
            members = {
                member.task_id: member
                for member in read_collection_status(
                    paths, collection_id
                ).record.review.members
            }
            hidden = []
            for task_id in task_ids:
                member = members[task_id]
                task_dir = paths.forge_build_dir(member.build_id) / "tasks" / task_id
                materials = [
                    ("reference_solution", _lines_under(task_dir / "solution")),
                    ("tests", _lines_under(task_dir / "tests")),
                ]
                if member.part == "held_out":
                    materials += [
                        ("instruction", _lines_of(task_dir / "instruction.md")),
                        (
                            "inputs",
                            _lines_under(task_dir / "environment", "Dockerfile"),
                        ),
                    ]
                hidden.append((task_id, materials, set()))
            return hidden


def _lines_under(directory: Path, *leaving_out: str) -> set[str]:
    """Return every stripped line of every text file under ``directory``,
    except the files at ``leaving_out``, relative to it."""
    return {
        line
        for path in sorted(p for p in directory.rglob("*") if p.is_file())
        if path.relative_to(directory).as_posix() not in leaving_out
        for line in _lines_of(path)
    }


def _lines_of(path: Path) -> set[str]:
    """Return every stripped line of one text file."""
    return {line.strip() for _, line in _text_lines(path)}


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


class _Measure(NamedTuple):
    """What one comparison says about its candidate on the tasks a verdict is over."""

    mean: float | None
    wins: int
    losses: int
    ties: int
    planned: int
    complete: bool


def _verdicts(
    parent: ForgeComparisonRecord, revised: ForgeComparisonRecord
) -> tuple[str, str | None]:
    """Return a revision's verdict and, on a collection, its study verdict.

    On a collection the verdict is over the held-out pairs alone, and the
    study verdict over the pairs of the tasks the reviser could see; on a
    build's tasks the one verdict is over them all.
    """
    if (
        parent.held_out is None
        or parent.study is None
        or revised.held_out is None
        or revised.study is None
    ):
        return (
            _verdict(
                "",
                parent,
                revised,
                _whole(parent),
                _whole(revised),
            ),
            None,
        )
    held_out = len(revised.held_out.task_ids)
    return (
        _verdict(
            f"On the {held_out} held-out {'task' if held_out == 1 else 'tasks'}, "
            "which the agent that wrote the revision never saw",
            parent,
            revised,
            _part(parent.held_out),
            _part(revised.held_out),
        ),
        _verdict(
            "On the tasks the agent that wrote the revision could see",
            parent,
            revised,
            _part(parent.study),
            _part(revised.study),
        ),
    )


def _whole(record: ForgeComparisonRecord) -> _Measure:
    return _Measure(
        mean=record.candidate.mean_reward,
        wins=record.wins,
        losses=record.losses,
        ties=record.ties,
        planned=record.pairs_planned,
        complete=record.complete,
    )


def _part(part: ForgePartSummary) -> _Measure:
    return _Measure(
        mean=part.candidate_mean_reward,
        wins=part.wins,
        losses=part.losses,
        ties=part.ties,
        planned=part.pairs_planned,
        complete=part.complete,
    )


def _verdict(
    scope: str,
    parent: ForgeComparisonRecord,
    revised: ForgeComparisonRecord,
    before: _Measure,
    after: _Measure,
) -> str:
    """Say, in one sentence, how the revision did against the Skill it revised."""
    partial = "" if before.complete and after.complete else " Partial evidence:"
    if before.mean is None or after.mean is None:
        placed = "the revision could not be placed"
        return sanitize_label(
            f"{partial} {f'{scope}, {placed}' if scope else placed.capitalize()} "
            "against the Skill it revised, because one of the two has no graded "
            "pair.".strip(),
            maximum=_VERDICT_LIMIT,
        )
    change = after.mean - before.mean
    word = (
        "improved on" if change > 0 else "regressed from" if change < 0 else "matched"
    )
    against = "against the same baseline"
    return sanitize_label(
        f"{partial} {f'{scope}, {against}' if scope else against.capitalize()}, "
        f"{revised.candidate_skill.name} {word} {parent.candidate_skill.name}: "
        f"mean reward {after.mean:.2f} against "
        f"{before.mean:.2f} ({change:+.2f}); {after.wins} won, {after.losses} lost, "
        f"{after.ties} tied of {after.planned}. Kept as measured.".strip(),
        maximum=_VERDICT_LIMIT,
    )
