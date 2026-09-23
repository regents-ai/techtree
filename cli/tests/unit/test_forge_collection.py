"""Accepting qualified tasks as one frozen collection (U4, AE5).

The tests hold what an acceptance promises: a collection shows every
proposed task with how it went, failures included, and accepts only the
qualified ones; nothing is frozen until a person accepts it; a collection of
fewer than three tasks is accepted with the few-tasks warning; a changed
byte in an accepted task, or a rewritten membership, fails verification; an
accepted collection is never accepted again, and a different membership is
a new version naming the one it replaces. The creator and Docker are the
stand-ins of the construction tests; no model is called.
"""

from __future__ import annotations

import json
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
from techtree.canonical import digest_object
from techtree.cli.app import create_app
from techtree.forge.collection import read_collection_status
from techtree.forge.construction import start_construction
from techtree.forge.models import ForgeBuildStatus, ForgeCollectionReview
from techtree.forge.planning import read_plan_status, start_plan
from techtree.forge.service import ForgeService, read_build_status
from techtree.forge.source import inspect_source_skill
from techtree.fs import atomic_write_json
from techtree.models.base import Digest
from techtree.paths import TechtreePaths, paths_from_root

SKILL = (
    "---\n"
    "name: branch-code\n"
    "description: Apply BranchCode v1 and return a BRANCH-XX token.\n"
    "license: MIT\n"
    "---\n\n"
    "1. Lowercase the input and keep only the letters a to z.\n"
)
QUALIFIES = "branch-code-single-word"
FAILS = "branch-code-batch"
REJECTED = "branch-code-audit"
TIMES_OUT = "branch-code-empty"
DOES_NOT_QUALIFY = "branch-code-unicode"
FIVE = [QUALIFIES, FAILS, REJECTED, TIMES_OUT, DOES_NOT_QUALIFY]


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
    """The planner's proposal, corrected by a person to the five tasks of AE5."""
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
    edited = json.loads(
        (paths.forge_proposal_dir(attempt.proposal_id) / "tasks.json").read_bytes()
    )
    for name in (TIMES_OUT, DOES_NOT_QUALIFY):
        edited["tasks"].append({**edited["tasks"][0], "name": name})
    corrected = tmp_path / "corrected.json"
    corrected.write_text(json.dumps(edited), encoding="utf-8")
    code, envelope = invoke(
        home, "correct-proposal", attempt.proposal_id, str(corrected)
    )
    assert code == 0, envelope
    corrected_id: str = envelope["facts"]["proposal_id"]
    return corrected_id


def invoke(home: Path, *arguments: str) -> tuple[int, dict[str, Any]]:
    result = CliRunner().invoke(
        create_app(), ["--home", str(home), "--json", "forge", *arguments]
    )
    return result.exit_code, json.loads(result.stdout)


def construct(
    home: Path,
    proposal_id: str,
    profiles: Path,
    creator: FakeCreator,
    *,
    retry_of: str | None = None,
) -> str:
    """Prepare and run one construction; only ``DOES_NOT_QUALIFY`` fails to qualify."""
    code, envelope = invoke(
        home,
        "construct",
        proposal_id,
        "--provider",
        "openai-codex",
        "--model",
        "gpt-5.6-sol",
        *(() if retry_of is None else ("--retry-of", retry_of)),
    )
    assert code == 0, envelope
    construction_id: str = envelope["facts"]["construction_id"]
    paths = paths_from_root(home)
    qualifying = FakeDocker(reward=0.0, reference_reward=1.0)
    # Tests that pass when nothing is done cannot tell a solution from none.
    passing = FakeDocker(reward=1.0)

    def qualify(
        task_dir: Path, source_skill: str, source_digest: Digest
    ) -> ForgeBuildStatus:
        run = passing if DOES_NOT_QUALIFY in task_dir.name else qualifying
        return ForgeService(paths, run, Path("/fake/uv")).import_skill(
            task_dir=task_dir, source_skill=source_skill, source_digest=source_digest
        )

    start_construction(
        paths,
        construction_id,
        reviewed_on="cli",
        answered_with="prompt",
        run=qualifying,
        qualify=qualify,
        launch=creator,
        profiles_root=profiles,
    )
    return construction_id


def ae5_creator() -> FakeCreator:
    """One task of each outcome: qualified, failed, rejected, unknown, unqualified."""
    answer = json.loads(created_package(REJECTED))
    answer["files"].append({"path": "task.toml", "text": "", "executable": False})
    return FakeCreator(
        calls={
            FAILS: FakePlanner(completed=False),
            REJECTED: FakePlanner(answer=json.dumps(answer).encode()),
            TIMES_OUT: FakePlanner(timed_out=True),
        }
    )


def collect(home: Path, *arguments: str) -> dict[str, Any]:
    code, envelope = invoke(home, "collect", *arguments)
    assert code == 0, envelope
    return envelope


def member_build(paths: TechtreePaths, collection_id: str) -> ForgeBuildStatus:
    [member] = read_collection_status(paths, collection_id).record.review.members
    return read_build_status(paths, member.build_id)


def test_five_proposed_one_qualified_all_shown_and_frozen_only_when_accepted(
    home: Path, proposal_id: str, profiles: Path
) -> None:
    construction_id = construct(home, proposal_id, profiles, ae5_creator())
    code, construction = invoke(home, "status", construction_id)
    assert code == 0
    assert [
        action["prepared_arguments"]["command"]
        for action in construction["next_actions"]
    ].count(["forge", "collect"]) == 1

    envelope = collect(home, construction_id)

    assert envelope["operation"] == "plan.prepare"
    status = envelope["facts"]
    review = status["record"]["review"]
    assert status["state"] == "prepared" and status["acceptance"] is None
    assert envelope["state_digest"] == status["record"]["collection_digest"]
    assert [task["task_name"] for task in review["tasks"]] == FIVE
    assert [(task["state"], task["usable"]) for task in review["tasks"]] == [
        ("succeeded", True),
        ("failed", False),
        ("rejected", False),
        ("outcome_unknown", False),
        ("succeeded", False),
    ]
    assert (
        review["tasks"][2]["why"] is not None
        and "task.toml" in (review["tasks"][2]["why"])
    )
    assert review["tasks"][4]["build_id"] is not None
    assert review["tasks"][4]["why"] is None
    [member] = review["members"]
    assert member["task_name"] == QUALIFIES
    assert review["version"] == 1 and review["previous"] is None
    [warning] = envelope["warnings"]
    assert warning["id"] == "forge_few_tasks"
    [accept] = envelope["next_actions"]
    assert accept["prepared_arguments"]["command"] == ["forge", "accept"]
    assert accept["expected_state_digest"] == status["record"]["collection_digest"]
    assert accept["approval_required"] is True
    collection_id = status["collection_id"]
    code, refused = invoke(home, "verify", collection_id)
    assert refused["error"]["code"] == "forge_collection_not_accepted"

    result = CliRunner().invoke(
        create_app(),
        ["--home", str(home), "forge", "accept", collection_id],
        input="y\n",
    )

    assert result.exit_code == 0, result.output
    for name in FIVE:
        assert name in result.output
    assert "built, but did not qualify" in result.output
    assert "outcome unknown" in result.output
    assert "Accept these tasks as the collection?" in result.output
    assert "Only 1 task is in this collection" in result.output
    accepted = read_collection_status(paths_from_root(home), collection_id)
    assert accepted.state == "accepted" and accepted.acceptance is not None
    assert accepted.acceptance.answered_with == "prompt"
    assert accepted.acceptance.collection_digest == accepted.record.collection_digest

    code, verified = invoke(home, "verify", collection_id)

    assert code == 0, verified
    assert verified["operation"] == "proof.verify"
    assert verified["warnings"][0]["id"] == "forge_few_tasks"
    code, again = invoke(home, "accept", collection_id, "--yes")
    assert again["error"]["code"] == "forge_collection_accepted"


def test_a_declined_collection_is_not_frozen(
    home: Path, proposal_id: str, profiles: Path
) -> None:
    construction_id = construct(home, proposal_id, profiles, ae5_creator())
    collection_id = collect(home, construction_id)["facts"]["collection_id"]

    result = CliRunner().invoke(
        create_app(),
        ["--home", str(home), "forge", "accept", collection_id],
        input="n\n",
    )

    assert result.exit_code != 0
    assert "the collection was not accepted, so nothing was frozen" in result.output
    status = read_collection_status(paths_from_root(home), collection_id)
    assert status.state == "prepared" and status.acceptance is None


def test_a_changed_byte_in_an_accepted_task_fails_verification(
    home: Path, proposal_id: str, profiles: Path
) -> None:
    paths = paths_from_root(home)
    construction_id = construct(home, proposal_id, profiles, ae5_creator())
    collection_id = collect(home, construction_id)["facts"]["collection_id"]
    assert invoke(home, "accept", collection_id, "--yes")[0] == 0
    build = member_build(paths, collection_id)
    [instruction] = Path(build.tasks_path).glob("*/instruction.md")
    instruction.write_bytes(instruction.read_bytes() + b" ")

    code, envelope = invoke(home, "verify", collection_id)

    assert code != 0
    assert envelope["error"]["code"] == "forge_collection_changed"
    assert envelope["error"]["details"]["cause"] == "forge_task_content_changed"


def test_a_rewritten_membership_fails_verification(
    home: Path, proposal_id: str, profiles: Path
) -> None:
    paths = paths_from_root(home)
    first = construct(home, proposal_id, profiles, ae5_creator())
    retry = construct(home, proposal_id, profiles, FakeCreator(), retry_of=first)
    collection_id = collect(home, retry, "--task", QUALIFIES)["facts"]["collection_id"]
    assert invoke(home, "accept", collection_id, "--yes")[0] == 0
    # Someone adds a qualified task to the accepted collection and makes every
    # digest in the record agree again; the acceptance still names the old one.
    path = paths.forge_collection_dir(collection_id) / "collection.json"
    record = json.loads(path.read_bytes())
    other = collect(home, retry)["facts"]["record"]["review"]
    record["review"]["members"] = other["members"]
    record["review"]["membership_digest"] = other["membership_digest"]
    record["collection_digest"] = digest_object(
        ForgeCollectionReview.model_validate_json(json.dumps(record["review"]))
    )
    atomic_write_json(path, record)

    code, envelope = invoke(home, "verify", collection_id)

    assert code != 0
    assert envelope["error"]["code"] == "forge_collection_changed"
    assert "changed after its acceptance" in envelope["error"]["message"]


def test_nothing_qualified_means_nothing_to_accept(
    home: Path, proposal_id: str, profiles: Path
) -> None:
    creator = FakeCreator(calls={name: FakePlanner(timed_out=True) for name in FIVE})
    construction_id = construct(home, proposal_id, profiles, creator)

    code, envelope = invoke(home, "collect", construction_id)

    assert code != 0
    assert envelope["error"]["code"] == "forge_collection_empty"
    code, construction = invoke(home, "status", construction_id)
    assert ["forge", "collect"] not in [
        action["prepared_arguments"]["command"]
        for action in construction["next_actions"]
    ]


def test_only_qualified_tasks_can_be_named(
    home: Path, proposal_id: str, profiles: Path
) -> None:
    construction_id = construct(home, proposal_id, profiles, ae5_creator())

    code, envelope = invoke(
        home, "collect", construction_id, "--task", DOES_NOT_QUALIFY
    )

    assert code != 0
    assert envelope["error"]["code"] == "forge_collection_task_not_usable"


def test_a_retried_task_joins_as_a_new_version(
    home: Path, proposal_id: str, profiles: Path
) -> None:
    first = construct(home, proposal_id, profiles, ae5_creator())
    v1 = collect(home, first)["facts"]["collection_id"]
    _, refused = invoke(home, "collect", first, "--previous", v1)
    assert refused["error"]["code"] == "forge_collection_not_accepted"
    assert invoke(home, "accept", v1, "--yes")[0] == 0
    _, refused = invoke(home, "collect", first, "--previous", v1)
    assert refused["error"]["code"] == "forge_collection_unchanged"
    retry = construct(home, proposal_id, profiles, FakeCreator(), retry_of=first)

    envelope = collect(home, retry, "--previous", v1)

    review = envelope["facts"]["record"]["review"]
    assert review["version"] == 2
    assert review["previous"]["collection_id"] == v1
    assert review["constructions"] == [retry, first]
    assert [member["task_name"] for member in review["members"]] == [
        QUALIFIES,
        FAILS,
        REJECTED,
        TIMES_OUT,
    ]
    assert envelope["warnings"] == []
    assert invoke(home, "verify", v1)[0] == 0
