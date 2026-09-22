"""Planning tasks from a Source Skill: review, approval, one call (U3b).

The tests hold what a planning approval promises: preparing writes the exact
text that would be sent and calls nothing; a declined plan calls nothing; an
approved plan calls the planner once, in the emptied profile, with no tools,
and keeps what it answered as a proposal that stops for review; a correction
is a new proposal and the original is untouched; a changed Hermes or Skill
copy refuses the old approval (AE3); and a call stopped mid-way is kept as an
unknown outcome that is never tried again without a new approval (AE4). The
planner is a stand-in that answers from a fixture; no model is called.
"""

from __future__ import annotations

import json
import subprocess
import sys
from functools import partial
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from fixtures.forge.support import (
    PLANNER_ANSWER,
    FakeDocker,
    FakePlanner,
    hermes_on_path,
    signed_in_profile,
)
from techtree.cli.app import create_app
from techtree.errors import ConflictError, RunError, ValidationError
from techtree.forge.planning import read_plan_status, start_plan
from techtree.forge.source import inspect_source_skill
from techtree.paths import TechtreePaths, paths_from_root

SKILL = (
    "---\n"
    "name: branch-code\n"
    "description: Apply BranchCode v1 and return a BRANCH-XX token.\n"
    "license: MIT\n"
    "---\n\n"
    "1. Lowercase the input and keep only the letters a to z.\n"
    "2. Read [the worked examples](references/examples.md).\n"
)
EXAMPLES = "maple gives BRANCH-74.\n"


@pytest.fixture
def home(temp_techtree_home: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    hermes_on_path(monkeypatch)
    return temp_techtree_home


@pytest.fixture
def source_id(tmp_path: Path, home: Path) -> str:
    root = tmp_path / "branch-code"
    (root / "references").mkdir(parents=True)
    (root / "SKILL.md").write_text(SKILL, encoding="utf-8")
    (root / "references" / "examples.md").write_text(EXAMPLES, encoding="utf-8")
    status = inspect_source_skill(paths_from_root(home), root, derived_from=None)
    assert status.record.state == "admitted"
    return status.source_id


def invoke(home: Path, *arguments: str) -> tuple[int, dict[str, Any]]:
    result = CliRunner().invoke(
        create_app(), ["--home", str(home), "--json", "forge", *arguments]
    )
    return result.exit_code, json.loads(result.stdout)


def prepare(home: Path, source_id: str, *extra: str) -> dict[str, Any]:
    code, envelope = invoke(
        home,
        "plan",
        source_id,
        "--provider",
        "openai-codex",
        "--model",
        "gpt-5.6-sol",
        "--tasks",
        "3",
        *extra,
    )
    assert code == 0, envelope
    return envelope


def starter(
    monkeypatch: pytest.MonkeyPatch, profiles: Path, planner: FakePlanner
) -> None:
    """Make ``forge plan-start`` call the stand-in planner in a test profile."""
    monkeypatch.setattr(
        "techtree.cli.commands.forge.start_plan",
        partial(start_plan, launch=planner, profiles_root=profiles),
    )
    monkeypatch.setattr("techtree.cli.commands.forge.run_command", FakeDocker())


def start(
    paths: TechtreePaths, plan_id: str, profiles: Path, planner: FakePlanner
) -> None:
    start_plan(
        paths,
        plan_id,
        reviewed_on="cli",
        answered_with="prompt",
        run=FakeDocker(),
        launch=planner,
        profiles_root=profiles,
    )


def test_preparing_writes_the_exact_prompt_and_calls_nothing(
    home: Path, source_id: str
) -> None:
    envelope = prepare(home, source_id)

    assert envelope["operation"] == "plan.prepare"
    status = envelope["facts"]
    record = status["record"]
    assert status["state"] == "prepared"
    assert envelope["state_digest"] == record["planning_digest"]
    review = record["review"]
    source = json.loads(
        (home / "forge" / "sources" / source_id / "source.json").read_bytes()
    )
    assert review["disclosure"]["files"] == source["admitted_files"]
    assert review["capabilities"] == {
        "tools": "none",
        "toolset": "bot_room",
        "memory_enabled": False,
    }
    assert review["limits"]["max_tasks"] == 3
    assert review["limits"]["attempts"] == 1
    prompt = (Path(status["path"]) / "prompt.md").read_bytes()
    assert len(prompt) == review["disclosure"]["prompt_bytes"]
    assert SKILL.encode() in prompt and EXAMPLES.encode() in prompt
    assert b"at most 3 distinct tasks" in prompt
    assert sorted(p.name for p in Path(status["path"]).iterdir()) == [
        "plan.json",
        "prompt.md",
    ]
    [action] = envelope["next_actions"]
    assert action["prepared_arguments"]["command"] == ["forge", "plan-start"]
    assert action["prepared_arguments"]["arguments"] == [status["plan_id"]]
    assert action["approval_required"] is True
    assert action["expected_state_digest"] == record["planning_digest"]
    assert action["data_egress"] == "model_provider"

    code, reviewed = invoke(home, "plan-start", status["plan_id"])
    assert code == 0
    assert reviewed["operation"] == "action.prepare"
    assert reviewed["facts"]["state"] == "prepared"
    assert reviewed["state_digest"] == record["planning_digest"]


def test_a_declined_plan_calls_nothing(
    home: Path,
    source_id: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan_id = prepare(home, source_id)["facts"]["plan_id"]
    planner = FakePlanner()
    starter(monkeypatch, tmp_path / "profiles", planner)

    result = CliRunner().invoke(
        create_app(),
        ["--home", str(home), "forge", "plan-start", plan_id],
        input="n\n",
    )

    assert result.exit_code != 0
    assert "What the model is sent" in result.output
    assert "Send this to the planner?" in result.output
    assert "the plan was not approved, so the planner was not called" in result.output
    assert planner.launches == []
    assert read_plan_status(paths_from_root(home), plan_id).state == "prepared"


def test_an_approved_plan_calls_the_planner_once_and_stops_at_a_proposal(
    home: Path,
    source_id: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = signed_in_profile(tmp_path / "profiles")
    (profile / "memories").mkdir()
    plan_id = prepare(home, source_id)["facts"]["plan_id"]
    planner = FakePlanner()
    starter(monkeypatch, tmp_path / "profiles", planner)

    code, envelope = invoke(
        home, "plan-start", plan_id, "--yes", "--reviewed-on", "host-agent"
    )

    assert code == 0, envelope
    assert envelope["operation"] == "action.execute"
    status = envelope["facts"]
    assert status["state"] == "succeeded"
    assert status["approval"]["reviewed_on"] == "host-agent"
    assert status["approval"]["answered_with"] == "yes-flag"
    assert status["approval"]["planning_digest"] == status["record"]["planning_digest"]
    [launch] = planner.launches
    argv = launch["argv"]
    assert isinstance(argv, list)
    assert argv[argv.index("-t") + 1] == "bot_room"
    assert "--ignore-rules" in argv and "--yolo" not in argv
    directory = Path(status["path"])
    assert argv[-1].encode() == (directory / "prompt.md").read_bytes()
    assert launch["profile"] == ["auth.json", "config.yaml", "techtree-run.lock"]
    assert sorted(p.name for p in profile.iterdir()) == [
        "auth.json",
        "techtree-run.lock",
    ]
    assert (directory / "state.db").read_bytes() == b"transcript"
    assert (directory / "answer.txt").read_bytes() == PLANNER_ANSWER
    attempt = status["attempt"]
    assert attempt["hermes_arguments"][-1] == "prompt.md"
    assert attempt["usage"]["api_calls"] == 1

    code, proposal = invoke(home, "status", attempt["proposal_id"])
    assert code == 0
    record = proposal["facts"]["record"]
    assert record["origin"] == "planner"
    assert record["plan_id"] == plan_id
    assert [task["name"] for task in record["tasks"]] == [
        "branch-code-single-word",
        "branch-code-batch",
        "branch-code-audit",
    ]

    code, again = invoke(home, "plan-start", plan_id, "--yes")
    assert again["error"]["code"] == "forge_planning_attempted"
    assert len(planner.launches) == 1


def test_a_correction_is_a_new_proposal_and_the_original_is_untouched(
    home: Path,
    source_id: str,
    tmp_path: Path,
) -> None:
    paths = paths_from_root(home)
    signed_in_profile(tmp_path / "profiles")
    plan_id = prepare(home, source_id)["facts"]["plan_id"]
    start(paths, plan_id, tmp_path / "profiles", FakePlanner())
    original_id = read_plan_status(paths, plan_id).attempt.proposal_id  # type: ignore[union-attr]
    original_dir = paths.forge_proposal_dir(str(original_id))
    original_bytes = (original_dir / "proposal.json").read_bytes()
    edited = json.loads((original_dir / "tasks.json").read_bytes())
    edited["tasks"] = edited["tasks"][:2]
    edited["tasks"][0]["success_criteria"].append("The file ends with a newline.")
    corrected = tmp_path / "corrected.json"
    corrected.write_text(json.dumps(edited), encoding="utf-8")

    code, envelope = invoke(home, "correct-proposal", str(original_id), str(corrected))

    assert code == 0, envelope
    record = envelope["facts"]["record"]
    parent = json.loads(original_bytes)
    assert record["origin"] == "contributor"
    assert record["parent"] == {
        "proposal_id": original_id,
        "proposal_digest": parent["proposal_digest"],
    }
    assert record["proposal_digest"] != parent["proposal_digest"]
    assert len(record["tasks"]) == 2
    assert envelope["state_digest"] == record["proposal_digest"]
    assert (original_dir / "proposal.json").read_bytes() == original_bytes

    code, unchanged = invoke(
        home, "correct-proposal", str(original_id), str(original_dir / "tasks.json")
    )
    assert unchanged["error"]["code"] == "forge_proposal_unchanged"


def test_a_changed_hermes_refuses_the_approval_it_was_not_given(
    home: Path,
    source_id: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = paths_from_root(home)
    signed_in_profile(tmp_path / "profiles")
    plan_id = prepare(home, source_id)["facts"]["plan_id"]
    monkeypatch.setattr(
        "techtree.forge.experiment.run_command",
        lambda argv, timeout: subprocess.CompletedProcess(
            list(argv), 0, "Hermes Agent v0.22.0 (2026.9.21) · upstream 1a2b3c4d\n", ""
        ),
    )
    planner = FakePlanner()

    with pytest.raises(ValidationError) as raised:
        start(paths, plan_id, tmp_path / "profiles", planner)

    assert raised.value.code == "forge_planning_stale"
    assert raised.value.details["changed"] == ["agent"]
    assert "the Hermes that would answer" in raised.value.message
    assert planner.launches == []
    assert read_plan_status(paths, plan_id).approval is None


def test_an_edited_skill_copy_is_refused_before_the_planner(
    home: Path,
    source_id: str,
    tmp_path: Path,
) -> None:
    paths = paths_from_root(home)
    signed_in_profile(tmp_path / "profiles")
    plan_id = prepare(home, source_id)["facts"]["plan_id"]
    kept = paths.forge_source_dir(source_id) / "skill" / "references" / "examples.md"
    kept.write_text("maple gives BRANCH-00.\n", encoding="utf-8")
    planner = FakePlanner()

    with pytest.raises(ValidationError) as raised:
        start(paths, plan_id, tmp_path / "profiles", planner)

    assert raised.value.code == "forge_source_changed"
    assert "references/examples.md" in raised.value.message
    assert planner.launches == []


def test_an_interrupted_call_is_an_unknown_outcome_and_never_retried(
    home: Path,
    source_id: str,
    tmp_path: Path,
) -> None:
    paths = paths_from_root(home)
    profile = signed_in_profile(tmp_path / "profiles")
    plan_id = prepare(home, source_id)["facts"]["plan_id"]
    planner = FakePlanner(interrupt=True)

    with pytest.raises(RunError) as raised:
        start(paths, plan_id, tmp_path / "profiles", planner)

    assert raised.value.code == "forge_planning_interrupted"
    assert sorted(p.name for p in profile.iterdir()) == [
        "auth.json",
        "techtree-run.lock",
    ]
    code, envelope = invoke(home, "status", plan_id)
    assert code == 0
    status = envelope["facts"]
    assert status["state"] == "outcome_unknown"
    assert status["attempt"]["stopped"] == "person"
    assert status["attempt"]["proposal_id"] is None
    [warning] = envelope["warnings"]
    assert warning["id"] == "forge_planning_outcome_unknown"
    [action] = envelope["next_actions"]
    assert action["prepared_arguments"]["command"] == ["forge", "plan"]
    assert action["prepared_arguments"]["options"]["--retry-of"] == plan_id

    with pytest.raises(ConflictError) as again:
        start(paths, plan_id, tmp_path / "profiles", FakePlanner())
    assert again.value.code == "forge_planning_attempted"

    retry = prepare(home, source_id, "--retry-of", plan_id)["facts"]
    assert retry["record"]["review"]["retry_of"] == plan_id
    assert retry["record"]["planning_digest"] != status["record"]["planning_digest"]
    assert len(planner.launches) == 1


def test_an_attempt_left_started_by_a_gone_process_reads_as_unknown(
    home: Path,
    source_id: str,
    tmp_path: Path,
) -> None:
    paths = paths_from_root(home)
    signed_in_profile(tmp_path / "profiles")
    plan_id = prepare(home, source_id)["facts"]["plan_id"]

    class Killed(BaseException):
        """What a process killed mid-call leaves: no chance to write an end."""

    def killed(*_: object) -> None:
        raise Killed

    with pytest.raises(Killed):
        start(paths, plan_id, tmp_path / "profiles", killed)  # type: ignore[arg-type]

    assert read_plan_status(paths, plan_id).state == "running"
    attempt_file = paths.forge_plan_dir(plan_id) / "attempt.json"
    attempt = json.loads(attempt_file.read_bytes())
    gone = subprocess.run(
        [sys.executable, "-c", "import os; print(os.getpid())"],
        capture_output=True,
        text=True,
        check=True,
    )
    attempt["process_id"] = int(gone.stdout)
    attempt_file.write_text(json.dumps(attempt), encoding="utf-8")

    status = read_plan_status(paths, plan_id)
    assert status.attempt is not None and status.attempt.state == "started"
    assert status.state == "outcome_unknown"


@pytest.mark.parametrize(
    ("answer", "code"),
    [
        (b"Here are some tasks you could try.", "forge_proposal_invalid"),
        (
            json.dumps(
                {
                    "tasks": [
                        *json.loads(PLANNER_ANSWER)["tasks"],
                        {**json.loads(PLANNER_ANSWER)["tasks"][0], "name": "fourth"},
                    ]
                }
            ).encode(),
            "forge_planner_too_many_tasks",
        ),
        (
            json.dumps(
                {
                    "tasks": [
                        {
                            **json.loads(PLANNER_ANSWER)["tasks"][0],
                            "success_criteria": [],
                        }
                    ]
                }
            ).encode(),
            "forge_proposal_invalid",
        ),
        (b" " * (64 * 1024 + 1), "forge_planner_answer_too_large"),
    ],
)
def test_an_answer_that_is_not_a_usable_proposal_is_rejected_and_kept(
    home: Path,
    source_id: str,
    tmp_path: Path,
    answer: bytes,
    code: str,
) -> None:
    paths = paths_from_root(home)
    signed_in_profile(tmp_path / "profiles")
    plan_id = prepare(home, source_id)["facts"]["plan_id"]

    start(paths, plan_id, tmp_path / "profiles", FakePlanner(answer=answer))

    status = read_plan_status(paths, plan_id)
    assert status.state == "rejected"
    assert status.attempt is not None and status.attempt.failure is not None
    assert status.attempt.failure.code == code
    assert (paths.forge_plan_dir(plan_id) / "answer.txt").read_bytes() == answer
    assert not paths.forge_proposals_dir.exists()


def test_a_skill_that_cannot_be_used_is_refused_before_anything_is_prepared(
    home: Path,
    tmp_path: Path,
) -> None:
    root = tmp_path / "branch-code"
    (root / "scripts").mkdir(parents=True)
    (root / "SKILL.md").write_text(
        SKILL.replace("references/examples.md", "scripts/run.sh"), encoding="utf-8"
    )
    (root / "scripts" / "run.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    refused = inspect_source_skill(paths_from_root(home), root, derived_from=None)

    code, envelope = invoke(
        home,
        "plan",
        refused.source_id,
        "--provider",
        "openai-codex",
        "--model",
        "gpt-5.6-sol",
    )

    assert code != 0
    assert envelope["error"]["code"] == "forge_skill_unsupported"
    assert "scripts/run.sh" in envelope["error"]["message"]
    assert not (home / "forge" / "plans").exists()
