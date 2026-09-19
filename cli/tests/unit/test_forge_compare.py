"""``forge compare``: two arms paired task by task, a record and a page.

The runs are made with the same stand-ins the run tests use, so what is
compared here is real run evidence on disk. The tests hold the three things
the comparison promises: a pair that differs anywhere but the Skill is
refused and nothing is written; a pair without a verdict on both sides is
unresolved, never a zero, and makes the whole comparison partial; and the
page says the same numbers as the record, on its own, with nothing fetched.
"""

from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from fixtures.forge.support import (
    FakeDocker,
    FakeHermes,
    QualifiedBuild,
    declare,
    qualified_build,
    write_skill,
)
from techtree.cli.app import create_app
from techtree.errors import NotFoundError, VerificationError
from techtree.forge.comparability import compare_run_specs
from techtree.forge.compare import (
    COMPARISON_FILENAME,
    REPORT_FILENAME,
    build_comparison,
    compare_runs,
    read_comparison_status,
)
from techtree.forge.models import (
    ForgeArm,
    ForgeAttemptOutcome,
    ForgeComparisonRecord,
    ForgePairResult,
    ForgeRunStatus,
)
from techtree.forge.run import ForgeRunner


@pytest.fixture
def build(temp_techtree_home: Path) -> QualifiedBuild:
    return qualified_build(temp_techtree_home)


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
    repetitions: int = 1,
    patch: str = "diff --git a/x b/x\n",
) -> ForgeRunStatus:
    spec = declare(
        build, monkeypatch, arm=arm, skill_root=skill, repetitions=repetitions
    )
    docker = FakeDocker(reward=reward, patch=patch)
    runner = ForgeRunner(
        build.paths, docker, launch=FakeHermes(), profiles_root=profiles
    )
    return runner.run(spec, skill)


# ---------------------------------------------------------------------------
# A controlled pair
# ---------------------------------------------------------------------------


def test_a_controlled_pair_is_paired_task_by_task_and_written(
    build: QualifiedBuild, skill: Path, profiles: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    baseline = run_arm(build, profiles, monkeypatch, arm=ForgeArm.BASELINE, reward=0.0)
    candidate = run_arm(
        build, profiles, monkeypatch, arm=ForgeArm.CANDIDATE, skill=skill, reward=1.0
    )

    status = compare_runs(build.paths, baseline.run_id, candidate.run_id)

    record = status.record
    assert record.baseline_run_id == baseline.run_id
    assert record.candidate_run_id == candidate.run_id
    assert record.build_id == build.build_id
    assert record.skill_name == "demo-skill"
    assert record.comparability.controlled
    assert record.complete
    assert (record.pairs_planned, record.pairs_graded) == (1, 1)
    assert (record.wins, record.losses, record.ties, record.unresolved) == (1, 0, 0, 0)
    assert record.mean_delta == 1.0
    pair = record.pairs[0]
    assert pair.task_id == build.task_id
    assert pair.result is ForgePairResult.WIN
    assert (pair.baseline_reward, pair.candidate_reward, pair.delta) == (0.0, 1.0, 1.0)
    assert record.baseline.mean_reward == 0.0
    assert record.candidate.mean_reward == 1.0
    assert record.candidate.attempts_graded == 1
    assert record.candidate.api_calls == 2
    assert record.candidate.total_tokens == 120
    assert record.candidate.cost_usd is None
    assert record.candidate.cost_statuses == ["unavailable"]
    assert "demo-skill won 1, lost 0 and tied 0" in record.summary
    assert not record.summary.startswith("Partial")

    directory = Path(status.path)
    assert directory == build.paths.forge_comparison_dir(status.comparison_id)
    assert (directory / COMPARISON_FILENAME).is_file()
    assert Path(status.report_path) == directory / REPORT_FILENAME
    assert Path(status.report_path).is_file()
    stored = ForgeComparisonRecord.model_validate_json(
        (directory / COMPARISON_FILENAME).read_bytes()
    )
    assert stored == record
    assert read_comparison_status(build.paths, status.comparison_id) == status


def test_equal_rewards_are_a_tie(
    build: QualifiedBuild, skill: Path, profiles: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    baseline = run_arm(build, profiles, monkeypatch, arm=ForgeArm.BASELINE, reward=1.0)
    candidate = run_arm(
        build, profiles, monkeypatch, arm=ForgeArm.CANDIDATE, skill=skill, reward=1.0
    )

    record = compare_runs(build.paths, baseline.run_id, candidate.run_id).record

    assert record.pairs[0].result is ForgePairResult.TIE
    assert (record.wins, record.losses, record.ties) == (0, 0, 1)
    assert record.mean_delta == 0.0


# ---------------------------------------------------------------------------
# The page
# ---------------------------------------------------------------------------


def test_the_report_is_one_self_contained_page_that_says_what_the_record_says(
    build: QualifiedBuild, skill: Path, profiles: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    baseline = run_arm(build, profiles, monkeypatch, arm=ForgeArm.BASELINE, reward=0.0)
    candidate = run_arm(
        build,
        profiles,
        monkeypatch,
        arm=ForgeArm.CANDIDATE,
        skill=skill,
        reward=1.0,
        patch="diff --git a/x b/x\n+<b>bold</b> & co\n",
    )

    status = compare_runs(build.paths, baseline.run_id, candidate.run_id)
    page = Path(status.report_path).read_text(encoding="utf-8")

    assert page.startswith("<!doctype html>")
    assert "<title>demo-skill on demo</title>" in page
    assert "Local evidence about a mutable subject" in page
    assert status.record.summary in page
    assert baseline.run_id in page and candidate.run_id in page
    assert "/repo/demo" in page
    assert 'class="win"' in page
    assert "no dollar figure (unavailable)" in page
    assert "+&lt;b&gt;bold&lt;/b&gt; &amp; co" in page
    assert "<b>bold</b>" not in page
    assert "<script" not in page
    assert "http://" not in page and "https://" not in page
    assert "<link" not in page
    for pointer in status.record.comparability.allowed_differences:
        assert f"<code>{pointer}</code>" in page
    for item in status.record.not_established:
        assert escape(item) in page


# ---------------------------------------------------------------------------
# Unresolved pairs
# ---------------------------------------------------------------------------


def test_an_attempt_without_a_verdict_leaves_its_pair_unresolved_and_the_result_partial(
    build: QualifiedBuild, skill: Path, profiles: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    baseline = run_arm(build, profiles, monkeypatch, arm=ForgeArm.BASELINE, reward=0.0)
    candidate = run_arm(
        build, profiles, monkeypatch, arm=ForgeArm.CANDIDATE, skill=skill, reward=None
    )

    status = compare_runs(build.paths, baseline.run_id, candidate.run_id)

    record = status.record
    pair = record.pairs[0]
    assert pair.candidate_outcome is ForgeAttemptOutcome.NO_VERDICT
    assert pair.candidate_reward is None
    assert pair.result is ForgePairResult.UNRESOLVED
    assert pair.delta is None
    assert not record.complete
    assert (record.pairs_graded, record.unresolved) == (0, 1)
    assert (record.wins, record.losses, record.ties) == (0, 0, 0)
    assert record.mean_delta is None
    assert record.summary.startswith("Partial: 0 of 1 planned pair has a verdict")
    assert "Nothing can be said about demo-skill yet." in record.summary
    page = Path(status.report_path).read_text(encoding="utf-8")
    assert 'class="unresolved"' in page
    assert "partial observation, not a complete result" in page


def test_an_attempt_never_reached_is_unresolved_not_a_zero(
    build: QualifiedBuild, skill: Path, profiles: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    baseline = run_arm(
        build, profiles, monkeypatch, arm=ForgeArm.BASELINE, reward=0.0, repetitions=2
    )
    candidate = run_arm(
        build,
        profiles,
        monkeypatch,
        arm=ForgeArm.CANDIDATE,
        skill=skill,
        reward=1.0,
        repetitions=2,
    )
    interrupted = baseline.model_copy(
        update={
            "record": baseline.record.model_copy(
                update={"attempts": baseline.record.attempts[:1], "state": "cancelled"}
            )
        }
    )

    record = build_comparison(
        interrupted,
        candidate,
        compare_run_specs(interrupted.spec, candidate.spec),
        comparison_id="forgecmp_" + "0" * 32,
        created_at=candidate.record.updated_at,
    )

    assert [pair.result for pair in record.pairs] == [
        ForgePairResult.WIN,
        ForgePairResult.UNRESOLVED,
    ]
    assert record.pairs[1].baseline_outcome is None
    assert record.pairs[1].baseline_reward is None
    assert record.baseline.state == "cancelled"
    assert (record.baseline.attempts_planned, record.baseline.attempts_recorded) == (
        2,
        1,
    )
    assert (record.pairs_graded, record.unresolved) == (1, 1)
    assert record.mean_delta == 1.0
    assert not record.complete
    assert record.summary.startswith("Partial: 1 of 2 planned pairs have a verdict")


# ---------------------------------------------------------------------------
# Refusals
# ---------------------------------------------------------------------------


def test_a_pair_that_differs_beyond_the_skill_is_refused_and_nothing_is_written(
    build: QualifiedBuild, skill: Path, profiles: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    baseline = run_arm(build, profiles, monkeypatch, arm=ForgeArm.BASELINE, reward=0.0)
    candidate = run_arm(
        build,
        profiles,
        monkeypatch,
        arm=ForgeArm.CANDIDATE,
        skill=skill,
        reward=1.0,
        repetitions=2,
    )

    with pytest.raises(VerificationError) as caught:
        compare_runs(build.paths, baseline.run_id, candidate.run_id)

    assert caught.value.code == "forge_comparison_invalid"
    assert "/sampling/repetitions" in str(caught.value)
    assert not build.paths.forge_comparisons_dir.exists()


def test_the_arms_must_be_given_as_baseline_then_candidate(
    build: QualifiedBuild, skill: Path, profiles: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    baseline = run_arm(build, profiles, monkeypatch, arm=ForgeArm.BASELINE, reward=0.0)
    candidate = run_arm(
        build, profiles, monkeypatch, arm=ForgeArm.CANDIDATE, skill=skill, reward=1.0
    )

    with pytest.raises(VerificationError) as caught:
        compare_runs(build.paths, candidate.run_id, baseline.run_id)
    assert caught.value.code == "forge_comparison_invalid"


def test_an_unknown_comparison_is_not_found(build: QualifiedBuild) -> None:
    with pytest.raises(NotFoundError) as caught:
        read_comparison_status(build.paths, "forgecmp_" + "f" * 32)
    assert caught.value.code == "forge_comparison_not_found"


# ---------------------------------------------------------------------------
# The command
# ---------------------------------------------------------------------------


def invoke(home: Path, *arguments: str) -> tuple[int, dict[str, Any]]:
    result = CliRunner().invoke(create_app(), ["--home", str(home), *arguments])
    return result.exit_code, json.loads(result.stdout)


def test_forge_compare_writes_the_comparison_and_forge_status_reads_it_back(
    build: QualifiedBuild, skill: Path, profiles: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    baseline = run_arm(build, profiles, monkeypatch, arm=ForgeArm.BASELINE, reward=0.0)
    candidate = run_arm(
        build, profiles, monkeypatch, arm=ForgeArm.CANDIDATE, skill=skill, reward=None
    )

    code, envelope = invoke(
        build.paths.root,
        "--json",
        "forge",
        "compare",
        baseline.run_id,
        candidate.run_id,
    )

    assert code == 0, envelope
    assert envelope["operation"] == "result.inspect"
    facts = envelope["facts"]
    assert isinstance(facts, dict)
    comparison_id = facts["comparison_id"]
    assert isinstance(comparison_id, str)
    assert facts["record"]["complete"] is False
    assert Path(facts["report_path"]).is_file()
    assert [w["id"] for w in envelope["warnings"]] == ["forge_comparison_partial"]
    action = envelope["next_actions"][0]
    assert action["operation"] == "plan.inspect"
    assert action["prepared_arguments"]["arguments"] == [comparison_id]
    assert action["data_egress"] == "none"

    code, shown = invoke(build.paths.root, "--json", "forge", "status", comparison_id)
    assert code == 0
    assert shown["operation"] == "plan.inspect"
    assert shown["facts"]["record"] == facts["record"]

    result = CliRunner().invoke(
        create_app(),
        [
            "--home",
            str(build.paths.root),
            "forge",
            "compare",
            baseline.run_id,
            candidate.run_id,
        ],
    )
    assert result.exit_code == 0, result.stdout
    human = " ".join(result.stdout.split())
    assert "no model was called" in human
    assert "0 won, 0 lost, 0 tied, 1 unresolved of 1 planned" in human
    assert "Partial:" in human
    assert "tests left no verdict" in human
    assert "Report" in human


def test_forge_compare_refuses_an_uncontrolled_pair_with_the_gate_code(
    build: QualifiedBuild, skill: Path, profiles: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    baseline = run_arm(build, profiles, monkeypatch, arm=ForgeArm.BASELINE, reward=0.0)
    candidate = run_arm(
        build,
        profiles,
        monkeypatch,
        arm=ForgeArm.CANDIDATE,
        skill=skill,
        reward=1.0,
        repetitions=2,
    )

    code, envelope = invoke(
        build.paths.root,
        "--json",
        "forge",
        "compare",
        baseline.run_id,
        candidate.run_id,
    )

    assert code == 11
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "forge_comparison_invalid"
