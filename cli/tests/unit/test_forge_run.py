"""Running one arm: what an attempt leaves, what it never touches, how it ends.

Docker and Hermes are stood in for at the run code's own seams; everything
else — the build reader, the specification, the run record, the profile, the
evidence layout — is the real thing writing into a temporary home.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from fixtures.forge.support import (
    AGENT_TIMEOUT,
    IMAGE_ID,
    INSTRUCTION,
    FakeDocker,
    FakeHermes,
    QualifiedBuild,
    declare,
    hermes_on_path,
    qualified_build,
    signed_in_profile,
    write_skill,
)
from techtree.canonical import sha256_digest_bytes
from techtree.cli.app import create_app
from techtree.errors import (
    ConflictError,
    NotFoundError,
    PrerequisiteError,
    RunError,
    ValidationError,
)
from techtree.forge.hermes import AgentOutcome
from techtree.forge.models import (
    ForgeArm,
    ForgeAttemptOutcome,
    ForgeEvidence,
    ForgeRunRecord,
    ForgeRunSpec,
    ForgeRunStatus,
)
from techtree.forge.profile import hermes_root, hold_profile
from techtree.forge.run import ForgeRunner, hermes_config, read_run_status


@pytest.fixture
def build(temp_techtree_home: Path) -> QualifiedBuild:
    return qualified_build(temp_techtree_home)


@pytest.fixture
def skill(tmp_path: Path) -> Path:
    return write_skill(tmp_path / "skills")


@pytest.fixture
def profiles(tmp_path: Path) -> Path:
    root = tmp_path / "hermes" / "profiles"
    signed_in_profile(root)
    return root


def runner(
    build: QualifiedBuild, docker: FakeDocker, hermes: FakeHermes, profiles: Path
) -> ForgeRunner:
    return ForgeRunner(build.paths, docker, launch=hermes, profiles_root=profiles)


def attempt_dir(status: ForgeRunStatus, task_id: str, attempt: int = 1) -> Path:
    return Path(status.path) / "tasks" / task_id / str(attempt)


# ---------------------------------------------------------------------------
# A graded attempt
# ---------------------------------------------------------------------------


def test_a_graded_attempt_records_reward_patch_usage_and_evidence(
    build: QualifiedBuild, profiles: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = declare(build, monkeypatch, arm=ForgeArm.BASELINE)
    docker, hermes = FakeDocker(reward=1.0), FakeHermes()

    status = runner(build, docker, hermes, profiles).run(spec, None)

    record = status.record
    assert record.state == "completed"
    assert record.failure is None
    assert len(record.attempts) == 1
    attempt = record.attempts[0]
    assert attempt.outcome is ForgeAttemptOutcome.GRADED
    assert attempt.reward == 1.0
    assert attempt.agent_exit_code == 0
    assert attempt.agent_timed_out is False
    assert attempt.usage is not None
    assert attempt.usage.total_tokens == 120
    assert attempt.usage.estimated_cost_usd is None
    assert attempt.usage.cost_status == "unavailable"
    assert attempt.patch_digest == sha256_digest_bytes(docker.patch.encode())
    assert attempt.evidence == [
        ForgeEvidence.USAGE_REPORT,
        ForgeEvidence.AGENT_TRANSCRIPT,
        ForgeEvidence.WORKSPACE_PATCH,
        ForgeEvidence.VERIFIER_VERDICT,
    ]

    where = attempt_dir(status, build.task_id)
    assert (where / "patch.diff").read_text() == docker.patch
    assert (where / "workspace" / "README.md").is_file()
    assert (where / "grading" / "verifier" / "reward.txt").is_file()
    assert (where / "state.db").read_bytes() == b"transcript"
    assert not (where / "auth.json").exists()
    assert attempt.config_digest == sha256_digest_bytes(
        (where / "config.yaml").read_bytes()
    )


def test_the_run_directory_holds_the_specification_and_the_record(
    build: QualifiedBuild, profiles: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = declare(build, monkeypatch, arm=ForgeArm.BASELINE)

    status = runner(
        build, profiles=profiles, docker=FakeDocker(), hermes=FakeHermes()
    ).run(spec, None)

    stored = ForgeRunSpec.model_validate_json(
        (Path(status.path) / "spec.json").read_bytes()
    )
    assert stored == spec
    record = ForgeRunRecord.model_validate_json(
        (Path(status.path) / "run.json").read_bytes()
    )
    assert record == status.record
    assert read_run_status(build.paths, status.run_id) == status


# ---------------------------------------------------------------------------
# What Hermes is started with
# ---------------------------------------------------------------------------


def test_hermes_runs_in_the_techtree_profile_emptied_of_all_but_the_sign_in(
    build: QualifiedBuild, profiles: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = declare(build, monkeypatch, arm=ForgeArm.BASELINE)
    hermes = FakeHermes()
    profile = profiles / "techtree"
    (profile / "memories").mkdir()
    (profile / "memories" / "MEMORY.md").write_text("earlier\n", encoding="utf-8")
    (profile / "state.db").write_bytes(b"an earlier session")

    status = runner(build, FakeDocker(), hermes, profiles).run(spec, None)

    launch = hermes.launches[0]
    assert launch["profile"] == profile
    assert launch["profile_files"] == ["auth.json", "config.yaml", "techtree-run.lock"]
    assert sorted(path.name for path in profile.iterdir()) == [
        "auth.json",
        "techtree-run.lock",
    ]
    env = launch["env"]
    assert isinstance(env, dict)
    assert env["HERMES_HOME"] == str(profile)
    assert env["HERMES_YOLO_MODE"] == "1"
    assert env["HERMES_ACCEPT_HOOKS"] == "1"
    assert launch["cwd"] == attempt_dir(status, build.task_id) / "workspace"
    assert launch["timeout"] == AGENT_TIMEOUT + 120.0


def test_a_run_without_the_techtree_profile_is_refused_before_anything_is_recorded(
    build: QualifiedBuild, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = declare(build, monkeypatch, arm=ForgeArm.BASELINE)
    hermes = FakeHermes()

    with pytest.raises(PrerequisiteError) as caught:
        runner(build, FakeDocker(), hermes, tmp_path / "nowhere").run(spec, None)

    assert caught.value.code == "forge_profile_missing"
    assert "hermes profile create techtree --no-alias" in caught.value.message
    assert hermes.launches == []
    assert not (build.paths.root / "forge" / "runs").exists()


def test_a_run_whose_profile_is_signed_out_is_refused_before_anything_is_recorded(
    build: QualifiedBuild, profiles: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = declare(build, monkeypatch, arm=ForgeArm.BASELINE)
    hermes = FakeHermes()

    with pytest.raises(PrerequisiteError) as caught:
        runner(build, FakeDocker(signed_in=False), hermes, profiles).run(spec, None)

    assert caught.value.code == "forge_profile_signed_out"
    assert "hermes -p techtree auth add openai-codex" in caught.value.message
    assert hermes.launches == []
    assert not (build.paths.root / "forge" / "runs").exists()


def test_a_second_run_in_the_profile_is_refused_while_the_first_holds_it(
    build: QualifiedBuild, profiles: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = declare(build, monkeypatch, arm=ForgeArm.BASELINE)
    hermes = FakeHermes()

    with hold_profile(profiles / "techtree"), pytest.raises(ConflictError) as caught:
        runner(build, FakeDocker(), hermes, profiles).run(spec, None)

    assert caught.value.code == "forge_profile_busy"
    assert hermes.launches == []
    assert not (build.paths.root / "forge" / "runs").exists()


def test_the_containers_hermes_left_behind_are_removed_by_profile_label(
    build: QualifiedBuild, profiles: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = declare(build, monkeypatch, arm=ForgeArm.BASELINE)
    docker = FakeDocker(left_behind=["abc123", "def456"])

    runner(build, docker, FakeHermes(), profiles).run(spec, None)

    listed = [call for call in docker.calls if call[:2] == ["docker", "ps"]]
    assert listed == [
        [
            "docker",
            "ps",
            "--all",
            "--quiet",
            "--filter",
            "label=hermes-profile=techtree",
        ]
    ]
    removed = [call[-1] for call in docker.calls if call[:2] == ["docker", "rm"]]
    assert removed[-2:] == ["abc123", "def456"]


def test_the_command_line_names_the_model_the_tools_and_the_instruction(
    build: QualifiedBuild, profiles: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = declare(build, monkeypatch, arm=ForgeArm.BASELINE)
    hermes = FakeHermes()

    status = runner(build, FakeDocker(), hermes, profiles).run(spec, None)

    argv = hermes.launches[0]["argv"]
    assert isinstance(argv, list)
    assert argv[0] == spec.agent.executable
    assert "--yolo" in argv
    assert argv[argv.index("-m") + 1] == "gpt-5.3-codex"
    assert argv[argv.index("--provider") + 1] == "openai-codex"
    assert argv[argv.index("-t") + 1] == "terminal,file,code_execution,skills"
    assert argv[-2:] == ["-z", INSTRUCTION]
    assert "-s" not in argv
    recorded = status.record.attempts[0].hermes_arguments
    assert recorded == [*argv[1:-1], "instruction.md"]
    assert INSTRUCTION not in recorded


def test_the_config_is_the_sandbox_the_specification_promises(
    build: QualifiedBuild, profiles: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = declare(build, monkeypatch, arm=ForgeArm.BASELINE)
    hermes = FakeHermes()

    status = runner(build, FakeDocker(), hermes, profiles).run(spec, None)

    config = hermes.launches[0]["config"]
    workspace = attempt_dir(status, build.task_id) / "workspace"
    assert isinstance(config, bytes)
    assert config == hermes_config(
        spec, IMAGE_ID, AGENT_TIMEOUT, workspace, "/workspace"
    )
    loaded = json.loads(config)
    assert loaded["terminal"]["backend"] == "docker"
    assert loaded["terminal"]["docker_image"] == IMAGE_ID
    assert loaded["terminal"]["docker_network"] is False
    assert loaded["terminal"]["docker_volumes"] == [f"{workspace}:/workspace"]
    assert loaded["terminal"]["cwd"] == "/workspace"
    assert loaded["terminal"]["container_cpu"] == spec.limits.container_cpus
    assert loaded["terminal"]["container_memory"] == spec.limits.container_memory_mb
    assert loaded["memory"]["memory_enabled"] is False
    assert loaded["agent"]["run_budget_seconds"] == AGENT_TIMEOUT
    assert loaded["auxiliary"]["title_generation"]["enabled"] is False


def test_the_candidate_arm_preloads_the_declared_skill_and_nothing_else(
    build: QualifiedBuild, skill: Path, profiles: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = declare(build, monkeypatch, arm=ForgeArm.CANDIDATE, skill_root=skill)
    hermes = FakeHermes()

    runner(build, FakeDocker(), hermes, profiles).run(spec, skill)

    launch = hermes.launches[0]
    assert launch["profile_files"] == [
        "auth.json",
        "config.yaml",
        "skills/demo-skill/SKILL.md",
        "techtree-run.lock",
    ]
    argv = launch["argv"]
    assert isinstance(argv, list)
    assert argv[argv.index("-s") + 1] == "demo-skill"


def test_a_skill_that_changed_since_declaration_does_not_run(
    build: QualifiedBuild, skill: Path, profiles: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = declare(build, monkeypatch, arm=ForgeArm.CANDIDATE, skill_root=skill)
    (skill / "SKILL.md").write_text("---\nname: demo-skill\n---\nChanged.\n")
    hermes = FakeHermes()

    with pytest.raises(ValidationError) as caught:
        runner(build, FakeDocker(), hermes, profiles).run(spec, skill)

    assert caught.value.code == "forge_skill_changed"
    assert hermes.launches == []
    assert not build.paths.forge_runs_dir.exists()


def test_the_arms_are_held_to_their_skill_at_run_time_too(
    build: QualifiedBuild, skill: Path, profiles: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    baseline = declare(build, monkeypatch, arm=ForgeArm.BASELINE)
    candidate = declare(build, monkeypatch, arm=ForgeArm.CANDIDATE, skill_root=skill)
    forge = runner(build, FakeDocker(), FakeHermes(), profiles)

    with pytest.raises(ValidationError) as with_skill:
        forge.run(baseline, skill)
    with pytest.raises(ValidationError) as without:
        forge.run(candidate, None)

    assert with_skill.value.code == "forge_baseline_with_skill"
    assert without.value.code == "forge_candidate_without_skill"


# ---------------------------------------------------------------------------
# Every other outcome
# ---------------------------------------------------------------------------


def test_an_agent_that_ran_out_of_time_is_not_graded(
    build: QualifiedBuild, profiles: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = declare(build, monkeypatch, arm=ForgeArm.BASELINE)
    docker = FakeDocker()

    status = runner(
        build, docker, FakeHermes(exit_code=None, timed_out=True), profiles
    ).run(spec, None)

    attempt = status.record.attempts[0]
    assert attempt.outcome is ForgeAttemptOutcome.AGENT_TIMED_OUT
    assert attempt.reward is None
    assert attempt.agent_timed_out is True
    assert attempt.agent_exit_code is None
    assert attempt.patch_digest is not None
    assert not docker.graded()
    assert status.record.state == "completed"


@pytest.mark.parametrize(
    ("hermes", "reason"),
    [
        (FakeHermes(exit_code=1), "a non-zero exit"),
        (FakeHermes(usage=None), "no usage report"),
        (
            FakeHermes(
                usage={"completed": False, "failed": True, "failure": "rate limited"}
            ),
            "a usage report that says it failed",
        ),
    ],
)
def test_an_agent_that_did_not_finish_is_not_graded(
    build: QualifiedBuild,
    profiles: Path,
    monkeypatch: pytest.MonkeyPatch,
    hermes: FakeHermes,
    reason: str,
) -> None:
    spec = declare(build, monkeypatch, arm=ForgeArm.BASELINE)
    docker = FakeDocker()

    status = runner(build, docker, hermes, profiles).run(spec, None)

    attempt = status.record.attempts[0]
    assert attempt.outcome is ForgeAttemptOutcome.AGENT_FAILED, reason
    assert attempt.reward is None
    assert not docker.graded()


def test_tests_that_ran_out_of_time_leave_no_reward(
    build: QualifiedBuild, profiles: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = declare(build, monkeypatch, arm=ForgeArm.BASELINE)

    status = runner(build, FakeDocker(reward="timeout"), FakeHermes(), profiles).run(
        spec, None
    )

    attempt = status.record.attempts[0]
    assert attempt.outcome is ForgeAttemptOutcome.VERIFIER_TIMED_OUT
    assert attempt.verifier_timed_out is True
    assert attempt.reward is None


def test_tests_that_left_nothing_readable_are_no_verdict_not_zero(
    build: QualifiedBuild, profiles: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = declare(build, monkeypatch, arm=ForgeArm.BASELINE)

    status = runner(build, FakeDocker(reward=None), FakeHermes(), profiles).run(
        spec, None
    )

    attempt = status.record.attempts[0]
    assert attempt.outcome is ForgeAttemptOutcome.NO_VERDICT
    assert attempt.reward is None
    assert ForgeEvidence.VERIFIER_VERDICT not in attempt.evidence


def test_a_zero_reward_is_a_graded_failure(
    build: QualifiedBuild, profiles: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = declare(build, monkeypatch, arm=ForgeArm.BASELINE)

    status = runner(build, FakeDocker(reward=0.0), FakeHermes(), profiles).run(
        spec, None
    )

    attempt = status.record.attempts[0]
    assert attempt.outcome is ForgeAttemptOutcome.GRADED
    assert attempt.reward == 0.0


def test_repetitions_run_in_order_each_in_its_own_workspace_and_a_fresh_profile(
    build: QualifiedBuild, profiles: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = declare(build, monkeypatch, arm=ForgeArm.BASELINE, repetitions=3)
    hermes = FakeHermes()

    status = runner(build, FakeDocker(), hermes, profiles).run(spec, None)

    assert [a.attempt for a in status.record.attempts] == [1, 2, 3]
    assert len({launch["cwd"] for launch in hermes.launches}) == 3
    assert [launch["profile_files"] for launch in hermes.launches] == [
        ["auth.json", "config.yaml", "techtree-run.lock"]
    ] * 3
    for number in (1, 2, 3):
        assert (attempt_dir(status, build.task_id, number) / "patch.diff").is_file()


# ---------------------------------------------------------------------------
# A run that does not finish keeps what it had
# ---------------------------------------------------------------------------


def test_an_infrastructure_failure_is_recorded_and_raised(
    build: QualifiedBuild, profiles: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = declare(build, monkeypatch, arm=ForgeArm.BASELINE)
    hermes = FakeHermes()

    with pytest.raises(RunError) as caught:
        runner(build, FakeDocker(export_error=True), hermes, profiles).run(spec, None)

    assert caught.value.code == "forge_workspace_export_failed"
    run_id = caught.value.details["run_id"]
    assert isinstance(run_id, str)
    status = read_run_status(build.paths, run_id)
    assert status.record.state == "failed"
    assert status.record.failure is not None
    assert status.record.failure.code == "forge_workspace_export_failed"
    assert status.record.attempts == []
    assert hermes.launches == []


def test_ctrl_c_during_an_attempt_keeps_earlier_attempts_and_empties_the_profile(
    build: QualifiedBuild, profiles: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = declare(build, monkeypatch, arm=ForgeArm.BASELINE, repetitions=2)
    hermes = FakeHermes()
    calls = 0

    def interrupt_second(
        argv: list[str], env: dict[str, str], cwd: Path, log: Path, timeout: float
    ) -> AgentOutcome:
        nonlocal calls
        calls += 1
        if calls == 2:
            hermes.interrupt = True
        return hermes(argv, env, cwd, log, timeout)

    with pytest.raises(RunError) as caught:
        ForgeRunner(
            build.paths, FakeDocker(), launch=interrupt_second, profiles_root=profiles
        ).run(spec, None)

    assert caught.value.code == "forge_run_cancelled"
    run_id = caught.value.details["run_id"]
    assert isinstance(run_id, str)
    status = read_run_status(build.paths, run_id)
    assert status.record.state == "cancelled"
    assert [a.attempt for a in status.record.attempts] == [1]
    assert sorted(path.name for path in (profiles / "techtree").iterdir()) == [
        "auth.json",
        "techtree-run.lock",
    ]


def test_a_build_whose_tasks_changed_since_declaration_does_not_run(
    build: QualifiedBuild, profiles: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = declare(build, monkeypatch, arm=ForgeArm.BASELINE)
    moved = spec.model_copy(
        update={
            "tasks_from": spec.tasks_from.model_copy(
                update={"membership_digest": "sha256:" + "0" * 64}
            )
        }
    )

    with pytest.raises(ValidationError) as caught:
        runner(build, FakeDocker(), FakeHermes(), profiles).run(moved, None)

    assert caught.value.code == "forge_membership_mismatch"


def test_reading_a_run_that_does_not_exist(build: QualifiedBuild) -> None:
    with pytest.raises(NotFoundError) as caught:
        read_run_status(build.paths, "forgerun_" + "0" * 32)
    assert caught.value.code == "forge_run_not_found"


def test_the_hermes_root_is_resolved_the_way_hermes_resolves_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("HERMES_HOME", raising=False)
    assert hermes_root() == Path.home() / ".hermes"
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "root"))
    assert hermes_root() == tmp_path / "root"
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "root" / "profiles" / "work"))
    assert hermes_root() == tmp_path / "root"


# ---------------------------------------------------------------------------
# The command
# ---------------------------------------------------------------------------


def invoke(home: Path, *arguments: str) -> tuple[int, dict[str, Any]]:
    result = CliRunner().invoke(create_app(), ["--home", str(home), *arguments])
    return result.exit_code, json.loads(result.stdout)


def test_forge_run_shows_the_review_and_starts_nothing_where_nobody_can_answer(
    build: QualifiedBuild, monkeypatch: pytest.MonkeyPatch
) -> None:
    hermes_on_path(monkeypatch)
    hermes = FakeHermes()
    monkeypatch.setattr(
        "techtree.cli.commands.forge.ForgeRunner",
        lambda paths, run: ForgeRunner(paths, FakeDocker(), launch=hermes),
    )

    code, envelope = invoke(
        build.paths.root,
        "--json",
        "forge",
        "run",
        "--arm",
        "baseline",
        "--build",
        build.build_id,
        "--provider",
        "openai-codex",
        "--model",
        "gpt-5.3-codex",
    )

    assert code == 0
    assert envelope["operation"] == "action.prepare"
    facts = envelope["facts"]
    assert isinstance(facts, dict)
    assert facts["attempts"] == 1
    review = facts["review"]
    assert isinstance(review, list)
    assert any("copies no credential" in line for line in review)
    assert any("nothing is quoted in advance" in line for line in review)
    actions = envelope["next_actions"]
    assert isinstance(actions, list) and len(actions) == 1
    action = actions[0]
    assert action["approval_required"] is True
    assert action["data_egress"] == "model_provider"
    assert action["expected_state_digest"] == facts["spec_digest"]
    assert action["prepared_arguments"]["options"]["--yes"] is True
    assert action["prepared_arguments"]["options"]["--build"] == build.build_id
    assert hermes.launches == []


def test_forge_run_with_yes_runs_and_forge_status_reads_it_back(
    build: QualifiedBuild, skill: Path, profiles: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hermes_on_path(monkeypatch)
    hermes = FakeHermes()
    monkeypatch.setattr(
        "techtree.cli.commands.forge.ForgeRunner",
        lambda paths, run: ForgeRunner(
            paths, FakeDocker(reward=None), launch=hermes, profiles_root=profiles
        ),
    )

    code, envelope = invoke(
        build.paths.root,
        "--json",
        "forge",
        "run",
        "--yes",
        "--arm",
        "candidate",
        "--build",
        build.build_id,
        "--provider",
        "openai-codex",
        "--model",
        "gpt-5.3-codex",
        "--skill",
        str(skill),
        "--tasks",
        build.task_id,
        "--reasoning",
        "high",
    )

    assert code == 0, envelope
    assert envelope["operation"] == "action.execute"
    facts = envelope["facts"]
    assert isinstance(facts, dict)
    run_id = facts["run_id"]
    assert isinstance(run_id, str)
    assert facts["record"]["state"] == "completed"
    assert [w["id"] for w in envelope["warnings"]] == ["forge_attempts_ungraded"]
    argv = hermes.launches[0]["argv"]
    assert isinstance(argv, list)
    assert argv[argv.index("--reasoning") + 1] == "high"

    code, shown = invoke(build.paths.root, "--json", "forge", "status", run_id)
    assert code == 0
    assert shown["operation"] == "plan.inspect"
    assert shown["facts"]["run_id"] == run_id
    assert shown["facts"]["record"]["attempts"][0]["outcome"] == "no_verdict"

    result = CliRunner().invoke(
        create_app(), ["--home", str(build.paths.root), "forge", "status", run_id]
    )
    assert result.exit_code == 0
    human = " ".join(result.stdout.split())
    assert "tests left no verdict" in human
    assert "no dollar figure" in human
