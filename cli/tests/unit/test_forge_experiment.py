"""The experiment's contract: what a run specification records and what may differ.

A specification is declared from checked facts, and two of them are comparable
only when nothing but the Skill differs. These tests hold both: the refusals
at declaration, and the gate's pointers.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError as ModelValidationError

from fixtures.forge.support import (
    HERMES_VERSION_LINE,
    FakeDocker,
    QualifiedBuild,
    declare,
    hermes_on_path,
    qualified_build,
    skill_build,
    write_skill,
)
from techtree.errors import PrerequisiteError, ValidationError, VerificationError
from techtree.forge.comparability import (
    ALLOWED_RUN_SPEC_DIFFERENCES,
    FORGE_COMPARISON_INVALID,
    assert_comparable_run_specs,
    compare_run_specs,
)
from techtree.forge.docker import Docker
from techtree.forge.experiment import (
    NOT_ESTABLISHED,
    declare_run_spec,
    run_spec_digest,
)
from techtree.forge.models import ForgeArm, ForgeBuildRecord, ForgeSkillSource
from techtree.forge.qualify import qualify_build
from techtree.forge.service import read_build_status
from techtree.paths import paths_from_root


@pytest.fixture
def build(temp_techtree_home: Path) -> QualifiedBuild:
    return qualified_build(temp_techtree_home)


@pytest.fixture
def skill(tmp_path: Path) -> Path:
    return write_skill(tmp_path / "skills")


# ---------------------------------------------------------------------------
# Declaration
# ---------------------------------------------------------------------------


def test_skill_build_preserves_content_without_repository_facts(tmp_path: Path) -> None:
    build = skill_build(tmp_path)
    paths = paths_from_root(tmp_path)
    status = read_build_status(paths, build.build_id)
    assert status.build == build
    assert isinstance(build.source, ForgeSkillSource)
    assert status.generation_finished is True
    assert status.qualification_finished is None
    assert status.progress is None
    assert [task.task_id for task in build.task_set.tasks] == ["reconcile-ledger"]
    with pytest.raises(PrerequisiteError) as caught:
        declare_run_spec(
            paths,
            arm=ForgeArm.BASELINE,
            build_id=build.build_id,
            task_ids=None,
            skill_root=None,
            provider="fixture",
            model_id="fixture",
            reasoning=None,
            repetitions=1,
        )
    assert caught.value.code == "forge_build_not_qualified"
    with pytest.raises(ValidationError) as caught_source:
        qualify_build(
            docker=Docker(FakeDocker()),
            build=build,
            tasks_dir=Path(status.tasks_path),
            work_dir=tmp_path / "qualification",
        )
    assert caught_source.value.code == "forge_source_unsupported"
    assert not (tmp_path / "qualification").exists()


def test_build_source_requires_one_complete_discriminated_identity(
    tmp_path: Path,
) -> None:
    build = skill_build(tmp_path)
    payload = build.model_dump(mode="json")
    for field in (
        "source_skill_digest",
        "recipe_version",
        "upstream_revision",
        "producer_version",
    ):
        invalid = build.model_dump(mode="json")
        del invalid["source"][field]
        with pytest.raises(ModelValidationError):
            ForgeBuildRecord.model_validate_json(json.dumps(invalid))
    for changes in (
        {"kind": "repository"},
        {"kind": "unknown"},
        {"head_commit": "a" * 40},
        {"upstream_revision": "main"},
    ):
        invalid = build.model_dump(mode="json")
        invalid["source"].update(changes)
        with pytest.raises(ModelValidationError):
            ForgeBuildRecord.model_validate_json(json.dumps(invalid))
    payload["repository"] = "/fake/repository"
    with pytest.raises(ModelValidationError):
        ForgeBuildRecord.model_validate_json(json.dumps(payload))


def test_old_build_schema_fails_without_changing_saved_bytes(
    build: QualifiedBuild,
) -> None:
    path = build.paths.forge_build_dir(build.build_id) / "build.json"
    payload = json.loads(path.read_bytes())
    source = payload.pop("source")
    source.pop("kind")
    payload.update(source)
    payload["schema_version"] = "techtree.forge-build.v1alpha2"
    original = json.dumps(payload).encode()
    path.write_bytes(original)
    with pytest.raises(ValidationError) as caught:
        read_build_status(build.paths, build.build_id)
    assert caught.value.code == "forge_schema_unsupported"
    assert caught.value.details["file"] == str(path)
    assert caught.value.details["schema_version"] == payload["schema_version"]
    assert path.read_bytes() == original


def test_a_baseline_records_the_build_and_the_facts_it_checked(
    build: QualifiedBuild, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = declare(build, monkeypatch, arm=ForgeArm.BASELINE, repetitions=2)

    assert spec.arm is ForgeArm.BASELINE
    assert spec.skill is None
    assert spec.build_id == build.build_id
    assert spec.task_ids == [build.task_id]
    assert spec.agent.executable == "/fake/bin/hermes"
    assert spec.agent.version == "0.21.3 (2026.9.14) · upstream 6d712cf8"
    assert f"Hermes Agent v{spec.agent.version}\n" == HERMES_VERSION_LINE
    assert spec.model.credential_source == "hermes-auth-store"
    assert spec.initial_state.memory_enabled is False
    assert spec.limits.network is False
    assert spec.sampling.repetitions == 2
    assert spec.grading.executed_by == "local-experiment"
    assert spec.not_established == list(NOT_ESTABLISHED)


def test_a_candidate_records_the_skill_by_name_and_content(
    build: QualifiedBuild, skill: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = declare(build, monkeypatch, arm=ForgeArm.CANDIDATE, skill_root=skill)

    assert spec.skill is not None
    assert spec.skill.name == "demo-skill"
    assert [file.path for file in spec.skill.files] == ["SKILL.md"]
    assert spec.skill.exposure == "preloaded"


def test_the_digest_follows_the_content(
    build: QualifiedBuild, skill: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = declare(build, monkeypatch, arm=ForgeArm.CANDIDATE, skill_root=skill)
    again = declare(build, monkeypatch, arm=ForgeArm.CANDIDATE, skill_root=skill)
    (skill / "SKILL.md").write_text("---\nname: demo-skill\n---\nChanged.\n")
    changed = declare(build, monkeypatch, arm=ForgeArm.CANDIDATE, skill_root=skill)

    assert run_spec_digest(first) == run_spec_digest(again)
    assert run_spec_digest(first) != run_spec_digest(changed)


def test_a_baseline_may_not_carry_a_skill(
    build: QualifiedBuild, skill: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(ValidationError) as caught:
        declare(build, monkeypatch, arm=ForgeArm.BASELINE, skill_root=skill)
    assert caught.value.code == "forge_baseline_with_skill"


def test_a_candidate_must_carry_a_skill(
    build: QualifiedBuild, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(ValidationError) as caught:
        declare(build, monkeypatch, arm=ForgeArm.CANDIDATE)
    assert caught.value.code == "forge_candidate_without_skill"


def test_only_qualified_tasks_can_be_named(
    build: QualifiedBuild, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(ValidationError) as caught:
        declare(
            build,
            monkeypatch,
            arm=ForgeArm.BASELINE,
            task_ids=[build.task_id, "local__other-000000000002"],
        )
    assert caught.value.code == "forge_task_not_qualified"
    assert caught.value.details["unqualified"] == ["local__other-000000000002"]


def test_a_build_that_qualified_nothing_declares_nothing(
    temp_techtree_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty = qualified_build(temp_techtree_home, qualified=False)
    with pytest.raises(ValidationError) as caught:
        declare(empty, monkeypatch, arm=ForgeArm.BASELINE)
    assert caught.value.code == "forge_no_usable_tasks"


def test_an_unqualified_build_is_a_missing_prerequisite(
    build: QualifiedBuild, monkeypatch: pytest.MonkeyPatch
) -> None:
    (build.paths.forge_build_dir(build.build_id) / "qualification.json").unlink()
    with pytest.raises(PrerequisiteError) as caught:
        declare(build, monkeypatch, arm=ForgeArm.BASELINE)
    assert caught.value.code == "forge_build_not_qualified"


def test_no_hermes_is_a_missing_prerequisite(
    build: QualifiedBuild, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("techtree.forge.experiment.shutil.which", lambda name: None)
    with pytest.raises(PrerequisiteError) as caught:
        declare_run_spec(
            build.paths,
            arm=ForgeArm.BASELINE,
            build_id=build.build_id,
            task_ids=None,
            skill_root=None,
            provider="openai-codex",
            model_id="gpt-5.3-codex",
            reasoning=None,
            repetitions=1,
        )
    assert caught.value.code == "hermes_not_found"


def test_a_hermes_without_a_version_banner_is_refused(
    build: QualifiedBuild, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess

    hermes_on_path(monkeypatch)
    monkeypatch.setattr(
        "techtree.forge.experiment.run_command",
        lambda argv, timeout: subprocess.CompletedProcess(list(argv), 0, "hi\n", ""),
    )
    with pytest.raises(PrerequisiteError) as caught:
        declare_run_spec(
            build.paths,
            arm=ForgeArm.BASELINE,
            build_id=build.build_id,
            task_ids=None,
            skill_root=None,
            provider="openai-codex",
            model_id="gpt-5.3-codex",
            reasoning=None,
            repetitions=1,
        )
    assert caught.value.code == "hermes_version_unreadable"


# ---------------------------------------------------------------------------
# The comparability gate
# ---------------------------------------------------------------------------


def test_a_controlled_pair_differs_only_in_arm_and_skill(
    build: QualifiedBuild, skill: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    baseline = declare(build, monkeypatch, arm=ForgeArm.BASELINE)
    candidate = declare(build, monkeypatch, arm=ForgeArm.CANDIDATE, skill_root=skill)

    comparison = compare_run_specs(baseline, candidate)

    assert comparison.controlled
    assert sorted(d.pointer for d in comparison.differences) == sorted(
        ALLOWED_RUN_SPEC_DIFFERENCES
    )
    assert comparison.violations == []
    assert_comparable_run_specs(comparison)


def test_any_other_difference_is_a_violation(
    build: QualifiedBuild, skill: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    baseline = declare(build, monkeypatch, arm=ForgeArm.BASELINE)
    candidate = declare(
        build, monkeypatch, arm=ForgeArm.CANDIDATE, skill_root=skill, repetitions=3
    )

    comparison = compare_run_specs(baseline, candidate)

    assert not comparison.controlled
    assert any("/sampling/repetitions" in v for v in comparison.violations)
    with pytest.raises(VerificationError) as caught:
        assert_comparable_run_specs(comparison)
    assert caught.value.code == FORGE_COMPARISON_INVALID


def test_the_arms_must_be_a_baseline_then_a_candidate(
    build: QualifiedBuild, skill: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    baseline = declare(build, monkeypatch, arm=ForgeArm.BASELINE)
    candidate = declare(build, monkeypatch, arm=ForgeArm.CANDIDATE, skill_root=skill)

    assert not compare_run_specs(candidate, baseline).controlled
    assert not compare_run_specs(baseline, baseline).controlled
