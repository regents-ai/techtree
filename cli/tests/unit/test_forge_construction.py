"""Building proposed tasks: review, approval, one pass of creator calls (U3b).

The tests hold what a construction approval promises: preparing writes each
call's exact prompt and calls nothing; a declined construction calls
nothing; an approved one calls the creator once per task and every package it
answers with goes through the same import, build and qualification as any
Skill2Env task; a call stopped at its time limit, a rejected answer and a
package that does not qualify are kept and shown, and nothing is called
twice; a corrected proposal refuses the old approval (AE3); Ctrl-C ends the
pass with the call under way kept as an unknown outcome (AE4); and trying
again is a new construction of only the tasks left without a usable package.
The creator is a stand-in that answers from a fixture and Docker a stand-in
that grades; no model is called.
"""

from __future__ import annotations

import json
import subprocess
import tomllib
from collections.abc import Sequence
from functools import partial
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from fixtures.forge.support import (
    FakeCreator,
    FakeDocker,
    FakePlanner,
    created_package,
    hermes_on_path,
    signed_in_profile,
)
from techtree.cli.app import create_app
from techtree.errors import PrerequisiteError, RunError, ValidationError
from techtree.forge.construction import (
    read_construction_status,
    start_construction,
)
from techtree.forge.planning import (
    read_plan_status,
    read_proposal_status,
    start_plan,
)
from techtree.forge.process import CommandRunner
from techtree.forge.service import ForgeService, read_build_status
from techtree.forge.source import inspect_source_skill
from techtree.paths import TechtreePaths, paths_from_root

SKILL = (
    "---\n"
    "name: branch-code\n"
    "description: Apply BranchCode v1 and return a BRANCH-XX token.\n"
    "license: MIT\n"
    "---\n\n"
    "1. Lowercase the input and keep only the letters a to z.\n"
)
TASKS = ["branch-code-single-word", "branch-code-batch", "branch-code-audit"]


@pytest.fixture
def home(temp_techtree_home: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    hermes_on_path(monkeypatch)
    return temp_techtree_home


@pytest.fixture
def profiles(tmp_path: Path) -> Path:
    signed_in_profile(tmp_path / "profiles")
    return tmp_path / "profiles"


@pytest.fixture
def proposal_id(tmp_path: Path, home: Path, profiles: Path) -> str:
    """The planner's proposal of TASKS, from a one-file BranchCode Skill."""
    root = tmp_path / "branch-code"
    root.mkdir()
    (root / "SKILL.md").write_text(SKILL, encoding="utf-8")
    paths = paths_from_root(home)
    source = inspect_source_skill(paths, root, derived_from=None)
    code, envelope = invoke(
        home,
        "plan",
        source.source_id,
        "--provider",
        "openai-codex",
        "--model",
        "gpt-5.6-sol",
    )
    assert code == 0, envelope
    plan_id = envelope["facts"]["plan_id"]
    start_plan(
        paths,
        plan_id,
        reviewed_on="cli",
        answered_with="prompt",
        run=FakeDocker(),
        launch=FakePlanner(),
        profiles_root=profiles,
    )
    attempt = read_plan_status(paths, plan_id).attempt
    assert attempt is not None and attempt.proposal_id is not None
    return attempt.proposal_id


def invoke(home: Path, *arguments: str) -> tuple[int, dict[str, Any]]:
    result = CliRunner().invoke(
        create_app(), ["--home", str(home), "--json", "forge", *arguments]
    )
    return result.exit_code, json.loads(result.stdout)


def prepare(home: Path, proposal_id: str, *extra: str) -> dict[str, Any]:
    code, envelope = invoke(
        home,
        "construct",
        proposal_id,
        "--provider",
        "openai-codex",
        "--model",
        "gpt-5.6-sol",
        *extra,
    )
    assert code == 0, envelope
    return envelope


def start(
    paths: TechtreePaths,
    construction_id: str,
    profiles: Path,
    creator: FakeCreator,
    docker: CommandRunner | None = None,
) -> None:
    """Start a construction whose packages are qualified against ``docker``."""
    run = docker if docker is not None else FakeDocker(reward=0.0, reference_reward=1.0)
    service = ForgeService(paths, run, Path("/fake/uv"))
    start_construction(
        paths,
        construction_id,
        reviewed_on="cli",
        answered_with="prompt",
        run=run,
        qualify=lambda task_dir, source_skill, source_digest: service.import_skill(
            task_dir=task_dir, source_skill=source_skill, source_digest=source_digest
        ),
        launch=creator,
        profiles_root=profiles,
    )


def starter(
    monkeypatch: pytest.MonkeyPatch,
    profiles: Path,
    creator: FakeCreator,
    docker: FakeDocker,
) -> None:
    """Make ``forge construct-start`` call the stand-ins in a test profile."""
    monkeypatch.setattr(
        "techtree.cli.commands.forge.start_construction",
        partial(start_construction, launch=creator, profiles_root=profiles),
    )
    monkeypatch.setattr("techtree.cli.commands.forge.run_command", docker)
    monkeypatch.setattr("techtree.cli.commands.forge.find_uv", lambda: Path("/fake/uv"))


def test_preparing_writes_each_prompt_and_calls_nothing(
    home: Path, proposal_id: str
) -> None:
    code, proposal = invoke(home, "status", proposal_id)
    assert code == 0
    [construct] = proposal["next_actions"]
    assert construct["prepared_arguments"]["command"] == ["forge", "construct"]
    assert construct["prepared_arguments"]["options"] == {
        "--provider": "openai-codex",
        "--model": "gpt-5.6-sol",
    }

    envelope = prepare(home, proposal_id)

    assert envelope["operation"] == "plan.prepare"
    status = envelope["facts"]
    record = status["record"]
    assert status["state"] == "prepared"
    assert envelope["state_digest"] == record["construction_digest"]
    review = record["review"]
    assert review["capabilities"] == {
        "tools": "none",
        "toolset": "bot_room",
        "memory_enabled": False,
    }
    assert review["limits"]["calls"] == 3
    assert review["limits"]["attempts_per_call"] == 1
    assert review["recipe"]["base_image"].startswith("python:3.12-slim@sha256:")
    suffix = status["construction_id"].split("_", 1)[1][:8]
    calls = review["disclosure"]["calls"]
    assert [call["task_name"] for call in calls] == TASKS
    proposed = read_proposal_status(paths_from_root(home), proposal_id).record
    tasks = {task.name: task.model_dump(mode="json") for task in proposed.tasks}
    claims = {
        claim.claim_id: claim.model_dump(mode="json") for claim in proposed.claims
    }
    assert review["claims"] == list(claims.values())
    for call in calls:
        assert call["package_name"] == f"task_{call['task_name']}_{suffix}"
        prompt = (
            Path(status["path"]) / "prompts" / f"{call['task_name']}.md"
        ).read_bytes()
        assert len(prompt) == call["prompt_bytes"]
        assert SKILL.encode() in prompt
        assert review["recipe"]["base_image"].encode() in prompt
        assert b"{base_image}" not in prompt
        task = tasks[call["task_name"]]
        assert (call["claim"], call["kind"]) == (task["claim"], task["kind"])
        for part in (claims[task["claim"]], task):
            assert json.dumps(part, indent=2, ensure_ascii=False).encode() in prompt
    [action] = envelope["next_actions"]
    assert action["prepared_arguments"]["command"] == ["forge", "construct-start"]
    assert action["expected_state_digest"] == record["construction_digest"]
    assert action["approval_required"] is True


def test_a_declined_construction_calls_nothing(
    home: Path,
    proposal_id: str,
    profiles: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    construction_id = prepare(home, proposal_id)["facts"]["construction_id"]
    creator = FakeCreator()
    starter(monkeypatch, profiles, creator, FakeDocker())

    result = CliRunner().invoke(
        create_app(),
        ["--home", str(home), "forge", "construct-start", construction_id],
        input="n\n",
    )

    assert result.exit_code != 0
    assert "What the model is sent, once for each task" in result.output
    assert "Send these tasks to the creator?" in result.output
    assert (
        "the construction was not approved, so the creator was not called"
        in result.output
    )
    assert creator.tasks == []
    status = read_construction_status(paths_from_root(home), construction_id)
    assert status.state == "prepared" and status.approval is None


def test_two_packages_and_one_unknown_outcome_are_shown_and_nothing_is_retried(
    home: Path,
    proposal_id: str,
    profiles: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    construction_id = prepare(home, proposal_id)["facts"]["construction_id"]
    creator = FakeCreator(calls={"branch-code-batch": FakePlanner(timed_out=True)})
    starter(
        monkeypatch, profiles, creator, FakeDocker(reward=0.0, reference_reward=1.0)
    )

    code, envelope = invoke(
        home, "construct-start", construction_id, "--yes", "--reviewed-on", "host-agent"
    )

    assert code == 0, envelope
    assert envelope["operation"] == "action.execute"
    assert creator.tasks == TASKS
    code, envelope = invoke(home, "status", construction_id)
    assert code == 0
    status = envelope["facts"]
    assert status["state"] == "finished"
    assert status["approval"]["answered_with"] == "yes-flag"
    tasks = {task["task_name"]: task for task in status["tasks"]}
    assert tasks["branch-code-batch"]["state"] == "outcome_unknown"
    assert tasks["branch-code-batch"]["call"]["stopped"] == "wall_time"
    assert tasks["branch-code-batch"]["package"] is None
    paths = paths_from_root(home)
    for name in ("branch-code-single-word", "branch-code-audit"):
        task = tasks[name]
        assert task["state"] == "succeeded"
        assert task["call"]["package_name"] == task["package_name"]
        package = task["package"]
        assert package["usable_tasks"] == 1 and package["failure"] is None
        build = read_build_status(paths, package["build_id"])
        assert build.usable_tasks == 1
        written = Path(status["path"]) / "calls" / name / task["package_name"]
        config = tomllib.loads((written / "task.toml").read_text(encoding="utf-8"))
        assert config["task"]["name"] == f"skill2env/{task['package_name']}"
        assert config["metadata"]["source_skill"] == "local/branch-code"
        assert (written / "tests" / "test.sh").stat().st_mode & 0o777 == 0o700
        assert (written / "instruction.md").stat().st_mode & 0o777 == 0o600
    [warning] = envelope["warnings"]
    assert warning["id"] == "forge_construction_outcome_unknown"
    assert "branch-code-batch" in warning["text"]
    actions = envelope["next_actions"]
    assert [action["prepared_arguments"]["command"] for action in actions] == [
        ["forge", "collect"],
        ["forge", "construct"],
        ["forge", "status"],
    ]
    assert actions[1]["prepared_arguments"]["options"]["--retry-of"] == (
        construction_id
    )

    result = CliRunner().invoke(
        create_app(), ["--home", str(home), "forge", "status", construction_id]
    )
    assert result.exit_code == 0
    assert "branch-code-batch: outcome unknown" in result.output
    assert result.output.count("usable, checked as build") == 2

    code, again = invoke(home, "construct-start", construction_id, "--yes")
    assert again["error"]["code"] == "forge_construction_attempted"
    assert creator.tasks == TASKS


def test_a_retry_builds_only_the_tasks_without_a_usable_package(
    home: Path, proposal_id: str, profiles: Path
) -> None:
    paths = paths_from_root(home)
    first = prepare(home, proposal_id)["facts"]["construction_id"]
    start(
        paths,
        first,
        profiles,
        FakeCreator(calls={"branch-code-batch": FakePlanner(completed=False)}),
    )
    assert read_construction_status(paths, first).tasks[1].state == "failed"

    retry = prepare(home, proposal_id, "--retry-of", first)["facts"]

    review = retry["record"]["review"]
    assert review["retry_of"] == first
    assert [call["task_name"] for call in review["disclosure"]["calls"]] == [
        "branch-code-batch"
    ]
    creator = FakeCreator()
    start(paths, retry["construction_id"], profiles, creator)
    assert creator.tasks == ["branch-code-batch"]
    _, refused = invoke(
        home,
        "construct",
        proposal_id,
        "--provider",
        "openai-codex",
        "--model",
        "gpt-5.6-sol",
        "--retry-of",
        retry["construction_id"],
    )
    assert refused["error"]["code"] == "forge_retry_not_needed"


def test_a_corrected_proposal_refuses_the_construction_approved_before(
    home: Path, proposal_id: str, profiles: Path, tmp_path: Path
) -> None:
    paths = paths_from_root(home)
    construction_id = prepare(home, proposal_id)["facts"]["construction_id"]
    edited = json.loads(
        (paths.forge_proposal_dir(proposal_id) / "claims-and-tasks.json").read_bytes()
    )
    edited["tasks"][0]["success_criteria"].append("The file ends with a newline.")
    corrected = tmp_path / "corrected.json"
    corrected.write_text(json.dumps(edited), encoding="utf-8")
    code, envelope = invoke(home, "correct-proposal", proposal_id, str(corrected))
    assert code == 0, envelope
    creator = FakeCreator()

    with pytest.raises(ValidationError) as raised:
        start(paths, construction_id, profiles, creator)

    assert raised.value.code == "forge_construction_stale"
    assert "the proposal's corrections" in raised.value.message
    assert raised.value.details["changed"] == ["corrected_by"]
    assert creator.tasks == []
    assert read_construction_status(paths, construction_id).approval is None
    [_, construct] = envelope["next_actions"]
    assert construct["prepared_arguments"]["arguments"] == [
        envelope["facts"]["proposal_id"]
    ]


def test_ctrl_c_ends_the_pass_and_the_call_under_way_is_unknown(
    home: Path, proposal_id: str, profiles: Path
) -> None:
    paths = paths_from_root(home)
    construction_id = prepare(home, proposal_id)["facts"]["construction_id"]
    creator = FakeCreator(calls={"branch-code-batch": FakePlanner(interrupt=True)})

    with pytest.raises(RunError) as raised:
        start(paths, construction_id, profiles, creator)

    assert raised.value.code == "forge_construction_interrupted"
    assert creator.tasks == TASKS[:2]
    status = read_construction_status(paths, construction_id)
    assert status.state == "stopped"
    assert [task.state for task in status.tasks] == [
        "succeeded",
        "outcome_unknown",
        "not_called",
    ]
    assert status.tasks[1].call is not None
    assert status.tasks[1].call.stopped == "person"
    assert sorted(p.name for p in (profiles / "techtree").iterdir()) == [
        "auth.json",
        "techtree-run.lock",
    ]


def test_an_answer_that_is_not_a_usable_package_is_rejected_and_kept(
    home: Path, proposal_id: str, profiles: Path
) -> None:
    paths = paths_from_root(home)
    construction_id = prepare(home, proposal_id)["facts"]["construction_id"]
    answer = json.loads(created_package("branch-code-audit"))
    answer["files"].append({"path": "task.toml", "text": "", "executable": False})
    bad = json.dumps(answer).encode()
    creator = FakeCreator(calls={"branch-code-audit": FakePlanner(answer=bad)})

    start(paths, construction_id, profiles, creator)

    audit = read_construction_status(paths, construction_id).tasks[2]
    assert audit.state == "rejected"
    assert audit.call is not None and audit.call.failure is not None
    assert audit.call.failure.code == "forge_creator_answer_invalid"
    assert "task.toml" in audit.call.failure.message
    assert audit.package is None
    directory = paths.forge_construction_dir(construction_id)
    assert (directory / "calls" / "branch-code-audit" / "answer.txt").read_bytes() == (
        bad
    )
    assert not (directory / "calls" / "branch-code-audit" / audit.package_name).exists()


def test_a_package_that_does_not_qualify_is_kept_as_not_usable(
    home: Path,
    proposal_id: str,
    profiles: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    construction_id = prepare(home, proposal_id)["facts"]["construction_id"]
    # Tests that pass when nothing is done cannot tell a solution from none.
    starter(monkeypatch, profiles, FakeCreator(), FakeDocker(reward=1.0))

    code, envelope = invoke(home, "construct-start", construction_id, "--yes")

    assert code != 0
    assert envelope["error"]["code"] == "forge_construction_nothing_usable"
    tasks = envelope["facts"]["tasks"]
    assert [task["package"]["usable_tasks"] for task in tasks] == [0, 0, 0]
    assert {task["package"]["failure"]["code"] for task in tasks} == {
        "forge_no_usable_tasks"
    }


def test_no_docker_means_no_call(home: Path, proposal_id: str, profiles: Path) -> None:
    paths = paths_from_root(home)
    construction_id = prepare(home, proposal_id)["facts"]["construction_id"]

    def no_docker(
        argv: Sequence[str], timeout: float
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(list(argv), 1, "", "Cannot connect\n")

    creator = FakeCreator()
    with pytest.raises(PrerequisiteError) as raised:
        start(paths, construction_id, profiles, creator, docker=no_docker)

    assert raised.value.code == "forge_docker_unavailable"
    assert creator.tasks == []
    assert read_construction_status(paths, construction_id).state == "prepared"


def test_only_a_finished_construction_of_the_same_proposal_is_retried(
    home: Path, proposal_id: str, profiles: Path, tmp_path: Path
) -> None:
    paths = paths_from_root(home)
    first = prepare(home, proposal_id)["facts"]["construction_id"]
    retry = (
        "construct",
        "--provider",
        "openai-codex",
        "--model",
        "gpt-5.6-sol",
        "--retry-of",
        first,
    )
    _, refused = invoke(home, *retry[:1], proposal_id, *retry[1:])
    assert refused["error"]["code"] == "forge_retry_not_needed"
    start(
        paths,
        first,
        profiles,
        FakeCreator(calls={"branch-code-audit": FakePlanner(timed_out=True)}),
    )
    edited = json.loads(
        (paths.forge_proposal_dir(proposal_id) / "claims-and-tasks.json").read_bytes()
    )
    edited["claims"] = edited["claims"][:1]
    edited["tasks"] = edited["tasks"][:1]
    corrected = tmp_path / "corrected.json"
    corrected.write_text(json.dumps(edited), encoding="utf-8")
    other = invoke(home, "correct-proposal", proposal_id, str(corrected))[1]

    _, refused = invoke(home, *retry[:1], other["facts"]["proposal_id"], *retry[1:])

    assert refused["error"]["code"] == "forge_retry_other_proposal"
