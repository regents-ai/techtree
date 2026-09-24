"""Accepting qualified tasks as one frozen collection (U4, AE5).

The tests hold what an acceptance promises: a collection shows every
proposed task with how it went, failures included, and accepts only the
qualified ones; nothing is frozen until a person accepts it; a collection of
fewer than three tasks is accepted with the few-tasks warning; a changed
byte in an accepted task, or a rewritten membership, fails verification; an
accepted collection is never accepted again, and a different membership is
a new version naming the one it replaces. A baseline runs on the accepted
collection (U4b, R35, R37): the subject works in the task's own working
directory with the tools and bounds the approved specification names, what
it left is recorded before any test runs, outputs that cannot be taken as
they are are not graded, and a missing required output still is; a
collection changed since it was declared, or a working directory that could
never be read back, stops the run before any agent starts. A baseline and a
candidate on the collection compare task by task, and the page says the
tasks were written from a Skill and shows what each attempt left. The creator,
Docker and Hermes are the stand-ins of the construction and run tests; no
model is called.
"""

from __future__ import annotations

import json
import stat
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from fixtures.forge.support import (
    FakeCreator,
    FakeDocker,
    FakeHermes,
    FakePlanner,
    created_package,
    hermes_on_path,
    signed_in_profile,
    write_skill,
)
from techtree.canonical import digest_object
from techtree.cli.app import create_app
from techtree.errors import RunError, TechtreeError, ValidationError
from techtree.forge.capture import MANIFEST_FILENAME
from techtree.forge.collection import read_collection_status
from techtree.forge.compare import compare_runs
from techtree.forge.construction import start_construction
from techtree.forge.experiment import declare_run_spec
from techtree.forge.models import (
    ForgeArm,
    ForgeAttemptOutcome,
    ForgeBuildStatus,
    ForgeCollectionReview,
    ForgeCollectionTasks,
    ForgeEvidence,
    ForgeOutputLimits,
    ForgeOutputManifest,
    ForgeRunSpec,
)
from techtree.forge.planning import read_plan_status, start_plan
from techtree.forge.run import ForgeRunner, read_run_status
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


# ---------------------------------------------------------------------------
# A baseline on the accepted collection
# ---------------------------------------------------------------------------


def accepted(home: Path, proposal_id: str, profiles: Path) -> str:
    """An accepted collection of the one task that qualified."""
    construction_id = construct(home, proposal_id, profiles, ae5_creator())
    collection_id: str = collect(home, construction_id)["facts"]["collection_id"]
    assert invoke(home, "accept", collection_id, "--yes")[0] == 0
    return collection_id


def baseline(home: Path, collection_id: str, *, repetitions: int = 1) -> ForgeRunSpec:
    return declare_run_spec(
        paths_from_root(home),
        arm=ForgeArm.BASELINE,
        collection_id=collection_id,
        task_ids=None,
        skill_root=None,
        provider="openai-codex",
        model_id="gpt-5.6-sol",
        reasoning=None,
        repetitions=repetitions,
    )


class GradingThatWrites(FakeDocker):
    """Docker whose tests leave a file in the directory they grade."""

    def __call__(
        self, argv: Sequence[str], timeout: float
    ) -> subprocess.CompletedProcess[str]:
        command = list(argv)
        if command[-1] == "bash /tests/test.sh":
            mounted = next(
                part.removesuffix(":/app") for part in command if part.endswith(":/app")
            )
            (Path(mounted) / "left-by-tests.txt").write_text("x\n", encoding="utf-8")
        return super().__call__(argv, timeout)


def test_a_baseline_on_the_accepted_collection_records_its_outputs_before_grading(
    home: Path, proposal_id: str, profiles: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    collection_id = accepted(home, proposal_id, profiles)
    docker = GradingThatWrites(reward=1.0)
    hermes = FakeHermes(
        leaves=lambda directory: (directory / "result.txt").write_text(
            "5\n", encoding="utf-8"
        )
    )
    monkeypatch.setattr(
        "techtree.cli.commands.forge.ForgeRunner",
        lambda paths, run: ForgeRunner(
            paths, docker, launch=hermes, profiles_root=profiles
        ),
    )
    options = [
        "run",
        "--arm",
        "baseline",
        "--collection",
        collection_id,
        "--provider",
        "openai-codex",
        "--model",
        "gpt-5.6-sol",
    ]
    code, review = invoke(home, *options)
    assert code == 0, review
    lines = review["facts"]["review"]
    assert f"Collection: {collection_id}, version 1, as accepted" in lines
    assert any("Before any test runs" in line for line in lines)
    [action] = review["next_actions"]
    assert action["prepared_arguments"]["options"]["--collection"] == collection_id
    assert hermes.launches == []

    code, envelope = invoke(home, *options, "--yes")

    assert code == 0, envelope
    status = read_run_status(paths_from_root(home), envelope["facts"]["run_id"])
    [attempt] = status.record.attempts
    assert attempt.outcome is ForgeAttemptOutcome.GRADED and attempt.reward == 1.0
    assert attempt.patch_digest is None
    assert ForgeEvidence.OUTPUT_MANIFEST in attempt.evidence
    assert ForgeEvidence.WORKSPACE_PATCH not in attempt.evidence
    outputs = attempt.outputs
    assert outputs is not None and outputs.failures == []
    assert (outputs.work_dir, outputs.added, outputs.modified) == ("/app", 1, 0)
    attempt_dir = Path(status.path) / "tasks" / attempt.task_id / "1"
    workspace = attempt_dir / "workspace"
    written = ForgeOutputManifest.model_validate_json(
        (attempt_dir / "outputs" / MANIFEST_FILENAME).read_bytes()
    )
    assert [change.path for change in written.changes] == ["result.txt"]
    assert (attempt_dir / "outputs" / "files" / "result.txt").read_text() == "5\n"
    assert (workspace / "left-by-tests.txt").is_file()
    written_config = hermes.launches[0]["config"]
    assert isinstance(written_config, bytes)
    config = json.loads(written_config)
    assert config["terminal"]["docker_volumes"] == [f"{workspace}:/app"]
    assert config["terminal"]["cwd"] == "/app"
    [grading] = [call for call in docker.calls if call[-1] == "bash /tests/test.sh"]
    assert f"{workspace}:/app" in grading
    shown = CliRunner().invoke(
        create_app(), ["--home", str(home), "forge", "status", status.run_id]
    )
    text = " ".join(shown.output.split())
    assert f"{collection_id} (version 1)" in text
    assert "1 added, 0 changed, 0 deleted in /app" in text
    assert "outputs read up to 10000 entries and 1 GB, keeping up to 64 MB" in text
    assert "Tools a shell, files, code and Skills" in text


def test_a_pair_on_the_collection_compares_and_says_its_tasks_came_from_a_skill(
    tmp_path: Path, home: Path, proposal_id: str, profiles: Path
) -> None:
    collection_id = accepted(home, proposal_id, profiles)
    paths = paths_from_root(home)
    skill = write_skill(tmp_path / "skills")
    hermes = FakeHermes(
        leaves=lambda directory: (directory / "result.txt").write_text(
            "5\n", encoding="utf-8"
        )
    )

    def run(spec: ForgeRunSpec, reward: float, skill_root: Path | None) -> str:
        runner = ForgeRunner(
            paths, FakeDocker(reward=reward), launch=hermes, profiles_root=profiles
        )
        return runner.run(spec, skill_root).run_id

    baseline_id = run(baseline(home, collection_id), 0.0, None)
    candidate_spec = declare_run_spec(
        paths,
        arm=ForgeArm.CANDIDATE,
        collection_id=collection_id,
        task_ids=None,
        skill_root=skill,
        provider="openai-codex",
        model_id="gpt-5.6-sol",
        reasoning=None,
        repetitions=1,
    )
    candidate_id = run(candidate_spec, 1.0, skill)

    status = compare_runs(paths, baseline_id, candidate_id)

    record = status.record
    assert isinstance(record.tasks_from, ForgeCollectionTasks)
    assert (record.tasks_from.collection_id, record.tasks_from.version) == (
        collection_id,
        1,
    )
    assert record.comparability.controlled
    assert (record.wins, record.losses) == (1, 0)
    page = Path(status.report_path).read_text(encoding="utf-8")
    assert f"<title>demo-skill on collection {collection_id}</title>" in page
    assert "Evaluation on Skill-derived tasks" in page
    assert f"{collection_id}, version 1" in page
    assert "complete these tasks, which were written from a Skill?" in page
    assert "1 added, 0 changed, 0 deleted in <code>/app</code>" in page
    assert "outputs/manifest.json" in page
    assert "Repository" not in page and "patch" not in page.lower()


def test_outputs_that_cannot_be_taken_are_not_graded_and_a_missing_one_still_is(
    home: Path, proposal_id: str, profiles: Path
) -> None:
    collection_id = accepted(home, proposal_id, profiles)
    left: list[str] = []

    def leaves(directory: Path) -> None:
        if not left:
            (directory / "result.txt").symlink_to("/etc/hostname")
        left.append(directory.name)

    docker = FakeDocker(reward=0.0)
    runner = ForgeRunner(
        paths_from_root(home),
        docker,
        launch=FakeHermes(leaves=leaves),
        profiles_root=profiles,
    )
    declared = baseline(home, collection_id, repetitions=2)
    limits = ForgeOutputLimits(entries=50, checked_bytes=5_000, kept_bytes=500)
    spec = declared.model_copy(
        update={
            "toolsets": ["terminal", "file"],
            "limits": declared.limits.model_copy(update={"outputs": limits}),
        }
    )

    status = runner.run(spec, None)

    rejected, missing = status.record.attempts
    assert rejected.outcome is ForgeAttemptOutcome.OUTPUTS_REJECTED
    assert rejected.reward is None
    assert ForgeEvidence.VERIFIER_VERDICT not in rejected.evidence
    assert rejected.outputs is not None
    assert [(f.kind, f.path) for f in rejected.outputs.failures] == [
        ("escaping_link", "result.txt")
    ]
    assert missing.outcome is ForgeAttemptOutcome.GRADED and missing.reward == 0.0
    assert missing.outputs is not None
    assert [(f.kind, f.path) for f in missing.outputs.failures] == [
        ("artifact_missing", "result.txt")
    ]
    assert [call[-1] for call in docker.calls].count("bash /tests/test.sh") == 1
    assert "terminal,file" in rejected.hermes_arguments
    attempt_dir = Path(status.path) / "tasks" / rejected.task_id / "1"
    written = ForgeOutputManifest.model_validate_json(
        (attempt_dir / "outputs" / MANIFEST_FILENAME).read_bytes()
    )
    assert written.limits == limits


def test_a_working_directory_that_cannot_give_back_its_outputs_does_not_run(
    home: Path, proposal_id: str, profiles: Path
) -> None:
    collection_id = accepted(home, proposal_id, profiles)
    declared = baseline(home, collection_id)
    tiny = declared.model_copy(
        update={
            "limits": declared.limits.model_copy(
                update={
                    "outputs": ForgeOutputLimits(
                        entries=50, checked_bytes=1, kept_bytes=1
                    )
                }
            )
        }
    )
    cases = [
        ("/", declared, "forge_work_dir_unusable"),
        ("/srv", declared, "forge_work_dir_unusable"),
        ("/app", tiny, "forge_work_dir_unreadable"),
    ]

    for work_dir, spec, code in cases:
        hermes = FakeHermes()
        runner = ForgeRunner(
            paths_from_root(home),
            FakeDocker(work_dir=work_dir),
            launch=hermes,
            profiles_root=profiles,
        )
        with pytest.raises(RunError) as caught:
            runner.run(spec, None)

        assert caught.value.code == code, work_dir
        recorded = read_run_status(
            paths_from_root(home), str(caught.value.details["run_id"])
        )
        assert recorded.record.state == "failed" and recorded.record.attempts == []
        assert hermes.launches == []


def test_a_collection_changed_since_its_declaration_does_not_run(
    home: Path, proposal_id: str, profiles: Path
) -> None:
    paths = paths_from_root(home)
    collection_id = accepted(home, proposal_id, profiles)
    spec = baseline(home, collection_id)
    hermes = FakeHermes()
    runner = ForgeRunner(paths, FakeDocker(), launch=hermes, profiles_root=profiles)
    assert isinstance(spec.tasks_from, ForgeCollectionTasks)
    other = spec.model_copy(
        update={
            "tasks_from": spec.tasks_from.model_copy(
                update={"collection_digest": "sha256:" + "0" * 64}
            )
        }
    )

    with pytest.raises(ValidationError) as mismatch:
        runner.run(other, None)
    [instruction] = Path(member_build(paths, collection_id).tasks_path).glob(
        "*/instruction.md"
    )
    instruction.write_bytes(instruction.read_bytes() + b" ")
    with pytest.raises(TechtreeError) as changed:
        runner.run(spec, None)

    assert mismatch.value.code == "forge_membership_mismatch"
    assert changed.value.code == "forge_collection_changed"
    assert hermes.launches == []


def test_a_run_is_declared_on_one_build_or_one_collection(
    home: Path, proposal_id: str, profiles: Path
) -> None:
    collection_id = accepted(home, proposal_id, profiles)
    build_id = member_build(paths_from_root(home), collection_id).build_id

    for sources in ({}, {"build_id": build_id, "collection_id": collection_id}):
        with pytest.raises(ValidationError) as caught:
            declare_run_spec(
                paths_from_root(home),
                arm=ForgeArm.BASELINE,
                task_ids=None,
                skill_root=None,
                provider="openai-codex",
                model_id="gpt-5.6-sol",
                reasoning=None,
                repetitions=1,
                **sources,
            )

        assert caught.value.code == "forge_run_tasks_unnamed"


# ---------------------------------------------------------------------------
# An export of the accepted collection
# ---------------------------------------------------------------------------


def test_an_export_is_checked_from_its_folder_alone_and_holds_nothing_private(
    home: Path, proposal_id: str, profiles: Path, tmp_path: Path
) -> None:
    paths = paths_from_root(home)
    collection_id = accepted(home, proposal_id, profiles)
    build = member_build(paths, collection_id)
    secret = "sk-decoy-4f1c9a7e2b"
    for place in (
        home / "auth.json",
        paths.forge_collection_dir(collection_id) / "notes.txt",
        Path(build.path) / "credentials.env",
    ):
        place.write_text(secret, encoding="utf-8")

    code, envelope = invoke(
        home, "export", collection_id, "--to", str(tmp_path / "export")
    )
    assert code == 0, envelope
    moved = tmp_path / "elsewhere"
    (tmp_path / "export").rename(moved)
    fresh = tmp_path / "fresh-home"
    fresh.mkdir()
    code, envelope = invoke(fresh, "verify-export", str(moved))

    assert code == 0, envelope
    assert envelope["facts"]["collection_id"] == collection_id
    assert build.build is not None
    [manifest] = build.build.task_set.tasks
    files = sorted(path for path in moved.rglob("*") if path.is_file())
    assert [str(path.relative_to(moved)) for path in files] == sorted(
        [
            "README.md",
            "export.json",
            *(
                f"tasks/{manifest.task_id}/{entry.path}"
                for entry in manifest.entries
                if entry.kind == "file"
            ),
        ]
    )
    for path in files:
        data = path.read_bytes()
        assert secret.encode() not in data, path
        assert b"keep only the letters a to z" not in data, path
    assert stat.S_IMODE(moved.stat().st_mode) == 0o700


def test_a_changed_or_added_file_in_an_export_is_refused_by_name(
    home: Path, proposal_id: str, profiles: Path, tmp_path: Path
) -> None:
    collection_id = accepted(home, proposal_id, profiles)
    export = tmp_path / "export"
    assert invoke(home, "export", collection_id, "--to", str(export))[0] == 0
    [task] = (export / "tasks").iterdir()
    instruction = task / "instruction.md"
    original = instruction.read_bytes()

    instruction.write_bytes(original + b" ")
    changed = invoke(home, "verify-export", str(export))
    instruction.write_bytes(original)
    (task / "tests" / "expected.json").write_text("{}", encoding="utf-8")
    added = invoke(home, "verify-export", str(export))

    for (code, envelope), name in (
        (changed, "instruction.md"),
        (added, "tests/expected.json"),
    ):
        assert code != 0
        assert envelope["error"]["code"] == "forge_export_changed"
        assert f"differ from what was accepted: {name}" in envelope["error"]["message"]
