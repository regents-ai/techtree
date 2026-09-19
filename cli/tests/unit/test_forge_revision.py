"""One revision cycle through ``uplift`` on a forge comparison.

The runs and comparisons are made with the same stand-ins the run and
compare tests use. The tests hold what the cycle promises: a run owns a
verified copy of the Skill it measured; the context a reviser reads carries
the task's instruction and result and none of the hidden material; a
revision is one Skill against the same baseline, screened rather than
refused; starting it is asked first, then runs, compares and records; and
the revision is kept whether it improved or regressed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from fixtures.forge.support import (
    FakeDocker,
    FakeHermes,
    QualifiedBuild,
    declare,
    hermes_on_path,
    qualified_build,
    write_skill,
)
from techtree.cli.app import create_app
from techtree.errors import PrerequisiteError, ValidationError, VerificationError
from techtree.forge.compare import compare_runs
from techtree.forge.improvement import build_forge_improvement_context
from techtree.forge.models import ForgeArm, ForgePairResult, ForgeRunStatus
from techtree.forge.revision import (
    measure_revision,
    prepare_revision,
    read_revision_status,
)
from techtree.forge.run import ForgeRunner
from techtree.forge.skill import SKILL_DIRNAME, read_owned_skill

PATCH_LINE = "+        return self.__class__.__members__[self.name]"
TEST_LINE = "    assert copy.deepcopy(Sentinel.UNSET) is Sentinel.UNSET"


@pytest.fixture
def build(temp_techtree_home: Path) -> QualifiedBuild:
    built = qualified_build(temp_techtree_home)
    (built.task_dir / "solution" / "patch.diff").write_text(
        "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@\n"
        f"{PATCH_LINE}\n+import enum\n",
        encoding="utf-8",
    )
    (built.task_dir / "tests" / "test_demo.py").write_text(
        f"def test_it():\n{TEST_LINE}\n", encoding="utf-8"
    )
    return built


@pytest.fixture
def skill(tmp_path: Path) -> Path:
    return write_skill(tmp_path / "skills")


@pytest.fixture
def profiles(tmp_path: Path) -> Path:
    return tmp_path / "profiles"


def run_arm(
    build: QualifiedBuild,
    profiles: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    arm: ForgeArm,
    skill: Path | None = None,
    reward: float | str | None,
) -> ForgeRunStatus:
    spec = declare(build, monkeypatch, arm=arm, skill_root=skill)
    runner = ForgeRunner(
        build.paths,
        FakeDocker(reward=reward),
        launch=FakeHermes(),
        profiles_root=profiles,
    )
    return runner.run(spec, skill)


def compared(
    build: QualifiedBuild,
    profiles: Path,
    monkeypatch: pytest.MonkeyPatch,
    skill: Path,
    *,
    baseline_reward: float = 0.0,
    candidate_reward: float = 0.5,
) -> str:
    """Return the id of a comparison of a baseline and a candidate run."""
    baseline = run_arm(
        build, profiles, monkeypatch, arm=ForgeArm.BASELINE, reward=baseline_reward
    )
    candidate = run_arm(
        build,
        profiles,
        monkeypatch,
        arm=ForgeArm.CANDIDATE,
        skill=skill,
        reward=candidate_reward,
    )
    return compare_runs(build.paths, baseline.run_id, candidate.run_id).comparison_id


def revised(tmp_path: Path, body: str = "Run the tests first, then read them.") -> Path:
    return write_skill(tmp_path / "revised", name="demo-skill-v2", body=body)


def invoke(home: Path, *arguments: str) -> tuple[int, dict[str, Any]]:
    result = CliRunner().invoke(create_app(), ["--home", str(home), *arguments])
    return result.exit_code, json.loads(result.stdout)


# ---------------------------------------------------------------------------
# The run owns its Skill
# ---------------------------------------------------------------------------


def test_a_candidate_run_keeps_its_own_copy_of_the_skill_and_serves_attempts_from_it(
    build: QualifiedBuild, skill: Path, profiles: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = declare(build, monkeypatch, arm=ForgeArm.CANDIDATE, skill_root=skill)
    hermes = FakeHermes()
    status = ForgeRunner(
        build.paths, FakeDocker(), launch=hermes, profiles_root=profiles
    ).run(spec, skill)

    copy = Path(status.path) / SKILL_DIRNAME / "SKILL.md"
    assert copy.read_bytes() == (skill / "SKILL.md").read_bytes()
    assert hermes.launches[0]["profile_files"] == [
        "config.yaml",
        "skills/demo-skill/SKILL.md",
    ]
    assert spec.skill is not None
    verified = read_owned_skill(
        spec.skill, Path(status.path) / SKILL_DIRNAME, owner_id=status.run_id
    )
    assert verified.root_digest == spec.skill.root_digest
    assert "Run the tests first." in verified.entrypoint_text


def test_a_baseline_run_keeps_no_skill(
    build: QualifiedBuild, profiles: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    status = run_arm(build, profiles, monkeypatch, arm=ForgeArm.BASELINE, reward=1.0)
    assert not (Path(status.path) / SKILL_DIRNAME).exists()


def test_a_tampered_copy_is_refused_not_returned(
    build: QualifiedBuild, skill: Path, profiles: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    status = run_arm(
        build, profiles, monkeypatch, arm=ForgeArm.CANDIDATE, skill=skill, reward=1.0
    )
    (Path(status.path) / SKILL_DIRNAME / "SKILL.md").write_text(
        "edited\n", encoding="utf-8"
    )
    assert status.spec.skill is not None

    with pytest.raises(VerificationError) as caught:
        read_owned_skill(
            status.spec.skill, Path(status.path) / SKILL_DIRNAME, owner_id=status.run_id
        )
    assert caught.value.code == "source_skill_unverified"


def test_uplift_skill_source_reads_a_forge_run_and_refuses_the_baseline(
    build: QualifiedBuild, skill: Path, profiles: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    baseline = run_arm(build, profiles, monkeypatch, arm=ForgeArm.BASELINE, reward=0.0)
    candidate = run_arm(
        build, profiles, monkeypatch, arm=ForgeArm.CANDIDATE, skill=skill, reward=1.0
    )

    code, envelope = invoke(
        build.paths.root, "--json", "uplift", "skill-source", candidate.run_id
    )
    assert code == 0
    assert envelope["operation"] == "plan.inspect"
    facts = envelope["facts"]
    assert facts["source_run_id"] == candidate.run_id
    assert facts["skill_name"] == "demo-skill"
    assert "Run the tests first." in facts["entrypoint_text"]

    code, envelope = invoke(
        build.paths.root, "--json", "uplift", "skill-source", baseline.run_id
    )
    assert code != 0
    assert envelope["error"]["code"] == "forge_candidate_without_skill"


# ---------------------------------------------------------------------------
# The context a reviser reads
# ---------------------------------------------------------------------------


def test_the_context_carries_the_instruction_and_the_result_and_nothing_hidden(
    build: QualifiedBuild, skill: Path, profiles: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comparison_id = compared(build, profiles, monkeypatch, skill)

    context = build_forge_improvement_context(build.paths, comparison_id)

    assert context.comparison_id == comparison_id
    assert context.repository == "demo"
    assert context.parent_skill_name == "demo-skill"
    assert context.current_result.wins == 1
    assert context.current_result.candidate_mean_reward == 0.5
    assert "rises above 0.500" in context.objective
    [example] = context.examples
    assert example.task_id == build.task_id
    assert example.result is ForgePairResult.WIN
    assert (example.baseline_reward, example.candidate_reward) == (0.0, 0.5)
    assert example.candidate_api_calls == 2
    assert "Make the failing test pass." in example.public_prompt
    serialized = context.model_dump_json()
    assert PATCH_LINE.strip("+ ") not in serialized
    assert TEST_LINE.strip() not in serialized
    assert "test_it" not in serialized
    assert str(build.paths.root) not in serialized
    assert "reference patch" in " ".join(context.prohibited_material)
    assert any("reference fix" in line for line in context.constraints)


def test_uplift_context_writes_the_context_beside_the_comparison(
    build: QualifiedBuild, skill: Path, profiles: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comparison_id = compared(build, profiles, monkeypatch, skill)

    code, envelope = invoke(
        build.paths.root, "--json", "uplift", "context", comparison_id
    )

    assert code == 0
    assert envelope["operation"] == "plan.prepare"
    facts = envelope["facts"]
    assert facts["relative_path"] == "improvement/context.json"
    written = build.paths.forge_comparison_dir(comparison_id) / "improvement"
    assert json.loads((written / "context.json").read_text())["comparison_id"] == (
        comparison_id
    )
    assert facts["context"]["schema_version"] == (
        "techtree.forge-improvement-context.v1alpha1"
    )
    assert [w["id"] for w in envelope["warnings"]] == [
        "improvement_context_is_not_proof"
    ]
    [action] = envelope["next_actions"]
    assert action["prepared_arguments"]["command"] == ["uplift", "skill-source"]
    assert action["prepared_arguments"]["arguments"] == [
        facts["context"]["candidate_run_id"]
    ]


def test_the_losses_are_listed_before_the_wins(
    build: QualifiedBuild, skill: Path, profiles: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    baseline = declare(build, monkeypatch, arm=ForgeArm.BASELINE, repetitions=2)
    candidate = declare(
        build, monkeypatch, arm=ForgeArm.CANDIDATE, skill_root=skill, repetitions=2
    )
    docker_baseline = FakeDocker(reward=0.5)
    docker_candidate = FakeDocker(reward=0.5)
    left = ForgeRunner(
        build.paths, docker_baseline, launch=FakeHermes(), profiles_root=profiles
    ).run(baseline, None)
    right = ForgeRunner(
        build.paths, docker_candidate, launch=FakeHermes(), profiles_root=profiles
    ).run(candidate, skill)
    # Rewrite the second candidate attempt as a loss, the first as a win, so
    # the record carries one of each in Campaign order win, loss.
    record_file = Path(right.path) / "run.json"
    record = json.loads(record_file.read_text())
    record["attempts"][0]["reward"] = 1.0
    record["attempts"][1]["reward"] = 0.0
    record_file.write_text(json.dumps(record))
    comparison_id = compare_runs(build.paths, left.run_id, right.run_id).comparison_id

    context = build_forge_improvement_context(build.paths, comparison_id)

    assert [e.result for e in context.examples] == [
        ForgePairResult.LOSS,
        ForgePairResult.WIN,
    ]
    assert [e.attempt for e in context.examples] == [2, 1]


# ---------------------------------------------------------------------------
# Preparing a revision
# ---------------------------------------------------------------------------


def test_a_revision_is_the_candidate_specification_with_the_skill_alone_replaced(
    build: QualifiedBuild,
    skill: Path,
    profiles: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    comparison_id = compared(build, profiles, monkeypatch, skill)

    status = prepare_revision(
        build.paths,
        comparison_id=comparison_id,
        skill_root=revised(tmp_path),
        label=None,
    )

    record = status.record
    assert record.state == "prepared"
    assert record.comparison_id == comparison_id
    assert record.skill.name == "demo-skill-v2"
    assert record.skill.root_digest != record.parent_skill_digest
    assert record.comparability.controlled
    assert [d.pointer for d in record.comparability.differences] == ["/arm", "/skill"]
    assert status.spec.skill == record.skill
    assert status.spec.model_copy(update={"skill": None, "arm": ForgeArm.BASELINE}) == (
        status.spec.model_copy(update={"skill": None, "arm": ForgeArm.BASELINE})
    )
    assert record.screening == []
    directory = Path(status.path)
    assert (directory / SKILL_DIRNAME / "SKILL.md").is_file()
    assert (directory / "spec.json").is_file()
    assert read_revision_status(build.paths, status.revision_id) == status


def test_a_label_names_the_revised_skill(
    build: QualifiedBuild,
    skill: Path,
    profiles: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    comparison_id = compared(build, profiles, monkeypatch, skill)

    status = prepare_revision(
        build.paths,
        comparison_id=comparison_id,
        skill_root=revised(tmp_path),
        label="tests-first",
    )
    assert status.record.skill.name == "tests-first"

    with pytest.raises(ValidationError) as caught:
        prepare_revision(
            build.paths,
            comparison_id=comparison_id,
            skill_root=revised(tmp_path / "again"),
            label="Tests First",
        )
    assert caught.value.code == "forge_skill_name_invalid"


def test_the_unchanged_skill_is_refused(
    build: QualifiedBuild, skill: Path, profiles: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    comparison_id = compared(build, profiles, monkeypatch, skill)

    with pytest.raises(ValidationError) as caught:
        prepare_revision(
            build.paths, comparison_id=comparison_id, skill_root=skill, label=None
        )

    assert caught.value.code == "forge_revision_unchanged"
    assert not build.paths.forge_revisions_dir.exists()


def test_a_hermes_that_changed_since_the_comparison_is_refused(
    build: QualifiedBuild,
    skill: Path,
    profiles: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    comparison_id = compared(build, profiles, monkeypatch, skill)
    monkeypatch.setattr(
        "techtree.forge.experiment.run_command",
        lambda argv, timeout: __import__("subprocess").CompletedProcess(
            list(argv), 0, "Hermes Agent v0.99.0 (2027.1.1)\n", ""
        ),
    )

    with pytest.raises(PrerequisiteError) as caught:
        prepare_revision(
            build.paths,
            comparison_id=comparison_id,
            skill_root=revised(tmp_path),
            label=None,
        )

    assert caught.value.code == "forge_agent_changed"
    assert not build.paths.forge_revisions_dir.exists()


def test_screening_records_lines_shared_with_the_fix_and_the_tests_without_refusing(
    build: QualifiedBuild,
    skill: Path,
    profiles: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    comparison_id = compared(build, profiles, monkeypatch, skill)
    leaky = revised(
        tmp_path,
        body=(
            "Write exactly this:\n\n"
            f"{PATCH_LINE[1:]}\n\n"
            f"{TEST_LINE}\n\n"
            "Make sure test_it passes afterwards.\n"
            "import enum\n"
        ),
    )

    status = prepare_revision(
        build.paths, comparison_id=comparison_id, skill_root=leaky, label=None
    )

    findings = [(f.material, f.line) for f in status.record.screening]
    assert ("reference_patch", 8) in findings
    assert ("tests", 10) in findings
    assert ("test_names", 12) in findings
    assert all(f.task_id == build.task_id for f in status.record.screening)
    # ``import enum`` is in the patch too, but too short to be evidence.
    assert not any(f.line == 13 for f in status.record.screening)
    assert status.record.state == "prepared"


def test_uplift_prepare_on_a_comparison_returns_the_revision_and_the_start_to_approve(
    build: QualifiedBuild,
    skill: Path,
    profiles: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    comparison_id = compared(build, profiles, monkeypatch, skill)

    code, envelope = invoke(
        build.paths.root,
        "--json",
        "uplift",
        "prepare",
        "--from-run",
        comparison_id,
        "--candidate-skill",
        str(revised(tmp_path)),
    )

    assert code == 0
    assert envelope["operation"] == "plan.prepare"
    facts = envelope["facts"]
    assert facts["record"]["state"] == "prepared"
    assert envelope["state_digest"] == facts["record"]["spec_digest"]
    [action] = envelope["next_actions"]
    assert action["operation"] == "action.execute"
    assert action["approval_required"] is True
    assert action["prepared_arguments"]["command"] == ["uplift", "start"]
    assert action["prepared_arguments"]["arguments"] == [facts["revision_id"]]
    assert action["prepared_arguments"]["options"] == {
        "--yes": True,
        "--reviewed-on": "host-agent",
    }
    assert action["expected_state_digest"] == facts["record"]["spec_digest"]


# ---------------------------------------------------------------------------
# Measuring a revision
# ---------------------------------------------------------------------------


def test_uplift_start_shows_the_review_and_runs_nothing_where_nobody_can_answer(
    build: QualifiedBuild,
    skill: Path,
    profiles: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    comparison_id = compared(build, profiles, monkeypatch, skill)
    revision = prepare_revision(
        build.paths,
        comparison_id=comparison_id,
        skill_root=revised(tmp_path),
        label=None,
    )
    hermes = FakeHermes()
    monkeypatch.setattr(
        "techtree.cli.commands.uplift.ForgeRunner",
        lambda paths, run: ForgeRunner(paths, FakeDocker(), launch=hermes),
    )

    code, envelope = invoke(
        build.paths.root, "--json", "uplift", "start", revision.revision_id
    )

    assert code == 0
    assert envelope["operation"] == "action.prepare"
    review = envelope["facts"]["review"]
    assert review[0].startswith(f"Revision: {revision.revision_id}")
    assert any("kept whether it improved or regressed" in line for line in review)
    assert any("Screening: no line" in line for line in review)
    assert any("copies no credential" in line for line in review)
    assert hermes.launches == []
    assert read_revision_status(build.paths, revision.revision_id).record.state == (
        "prepared"
    )


def test_uplift_start_with_yes_runs_compares_and_keeps_a_regression(
    build: QualifiedBuild,
    skill: Path,
    profiles: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    comparison_id = compared(build, profiles, monkeypatch, skill, candidate_reward=1.0)
    revision = prepare_revision(
        build.paths,
        comparison_id=comparison_id,
        skill_root=revised(tmp_path),
        label=None,
    )
    hermes = FakeHermes()
    monkeypatch.setattr(
        "techtree.cli.commands.uplift.ForgeRunner",
        lambda paths, run: ForgeRunner(
            paths, FakeDocker(reward=0.0), launch=hermes, profiles_root=profiles
        ),
    )

    code, envelope = invoke(
        build.paths.root,
        "--json",
        "uplift",
        "start",
        "--yes",
        "--reviewed-on",
        "host-agent",
        revision.revision_id,
    )

    assert code == 0
    assert envelope["operation"] == "action.execute"
    facts = envelope["facts"]
    record = facts["revision"]["record"]
    assert record["state"] == "measured"
    assert record["measured_run_id"] == facts["run"]["run_id"]
    assert record["measured_comparison_id"] == facts["comparison"]["comparison_id"]
    assert "regressed from demo-skill" in record["verdict"]
    assert "0.00 against 1.00 (-1.00)" in record["verdict"]
    assert record["verdict"].endswith("Kept as measured.")
    assert (
        facts["comparison"]["record"]["baseline_run_id"]
        == (facts["revision"]["record"]["baseline_run_id"])
    )
    assert facts["comparison"]["record"]["skill_name"] == "demo-skill-v2"
    assert facts["run"]["spec"]["skill"]["name"] == "demo-skill-v2"
    [launch] = hermes.launches
    assert launch["profile_files"] == ["config.yaml", "skills/demo-skill-v2/SKILL.md"]
    assert (
        read_revision_status(build.paths, revision.revision_id).record.state
        == "measured"
    )

    code, envelope = invoke(
        build.paths.root, "--json", "forge", "status", revision.revision_id
    )
    assert code == 0
    assert envelope["facts"]["record"]["verdict"] == record["verdict"]


def test_a_measured_revision_is_not_measured_again(
    build: QualifiedBuild,
    skill: Path,
    profiles: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    comparison_id = compared(build, profiles, monkeypatch, skill)
    revision = prepare_revision(
        build.paths,
        comparison_id=comparison_id,
        skill_root=revised(tmp_path),
        label=None,
    )
    runner = ForgeRunner(
        build.paths, FakeDocker(reward=1.0), launch=FakeHermes(), profiles_root=profiles
    )
    measured = measure_revision(build.paths, revision.revision_id, runner)
    assert "improved on demo-skill" in (measured.revision.record.verdict or "")

    with pytest.raises(ValidationError) as caught:
        measure_revision(build.paths, revision.revision_id, runner)

    assert caught.value.code == "forge_revision_measured"
    assert len(list(build.paths.forge_runs_dir.iterdir())) == 3


def test_uplift_start_without_yes_on_a_declared_surface_is_refused(
    build: QualifiedBuild,
    skill: Path,
    profiles: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    comparison_id = compared(build, profiles, monkeypatch, skill)
    revision = prepare_revision(
        build.paths,
        comparison_id=comparison_id,
        skill_root=revised(tmp_path),
        label=None,
    )
    hermes_on_path(monkeypatch)

    code, envelope = invoke(
        build.paths.root,
        "--json",
        "uplift",
        "start",
        "--reviewed-on",
        "host-agent",
        revision.revision_id,
    )

    assert code != 0
    assert envelope["error"]["code"] == "review_surface_not_approved"
