"""Accepting qualified tasks as one frozen collection (U4, AE5).

The tests hold what an acceptance promises: a collection shows every
proposed task with how it went, failures included, and accepts only the
qualified ones; nothing is frozen until a person accepts it; a collection of
fewer than three tasks is accepted with the few-tasks warning, and one of a
single task is refused; a changed
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
tasks were written from a Skill and shows what each attempt left. Every
Skill keeps its own role there (T13, R19, R36, AE8): the Source Skill, the
baseline's Skill if it has one, and the candidate's, each by its own digest
even when two are the same bytes. A Skill-v1-to-Skill-v2 comparison is
judged by the same rules, a run on a different version of the collection is
not comparable, and a comparison on the collection is revised there, screened
against the tasks' reference solutions and tests. Which tasks are held out
follows from the tasks alone, whatever order they come in, and puts a task in
each part (founder decision 2a); the improving agent's context never names a
held-out task or shows its instruction, and a revision's verdict is worked
out on the held-out tasks alone. The creator, Docker and Hermes are the
stand-ins of the construction and run tests; no model is called.
"""

from __future__ import annotations

import hashlib
import json
import shutil
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
from techtree.errors import RunError, TechtreeError, ValidationError, VerificationError
from techtree.forge.capture import MANIFEST_FILENAME
from techtree.forge.collection import read_collection_status
from techtree.forge.comparability import (
    assert_comparable_run_specs,
    compare_run_specs,
)
from techtree.forge.compare import compare_runs
from techtree.forge.construction import start_construction
from techtree.forge.experiment import declare_run_spec
from techtree.forge.improvement import (
    ForgeImprovementCollection,
    build_forge_improvement_context,
)
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
    ForgeVerdict,
    collection_parts,
)
from techtree.forge.planning import read_plan_status, start_plan
from techtree.forge.revision import (
    measure_revision,
    prepare_revision,
    read_revision_status,
)
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
ALSO_QUALIFIES = "branch-code-twice"
PROPOSED = [QUALIFIES, FAILS, REJECTED, TIMES_OUT, DOES_NOT_QUALIFY, ALSO_QUALIFIES]


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
    root = tmp_path / "branch-code"
    root.mkdir()
    (root / "SKILL.md").write_text(SKILL, encoding="utf-8")
    source = inspect_source_skill(paths_from_root(home), root, lineage=None)
    return propose(tmp_path, home, profiles, source.source_id)


def propose(tmp_path: Path, home: Path, profiles: Path, source_id: str) -> str:
    """The planner's proposal, corrected by a person to the five tasks of AE5
    and one more that qualifies, so that a collection has a task in each part."""
    paths = paths_from_root(home)
    code, envelope = invoke(
        home,
        "plan",
        source_id,
        "--provider",
        "openai-codex",
        "--model",
        "gpt-5.6-sol",
        "--tasks",
        str(len(PROPOSED)),
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
        (
            paths.forge_proposal_dir(attempt.proposal_id) / "claims-and-tasks.json"
        ).read_bytes()
    )
    for name in (TIMES_OUT, DOES_NOT_QUALIFY, ALSO_QUALIFIES):
        edited["tasks"].append({**edited["tasks"][0], "name": name})
    corrected = tmp_path / f"corrected-{source_id}.json"
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
    """One task of each outcome: qualified, failed, rejected, unknown, unqualified;
    and the one more that qualifies."""
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
    member = read_collection_status(paths, collection_id).record.review.members[0]
    return read_build_status(paths, member.build_id)


def test_six_proposed_two_qualified_all_shown_and_frozen_only_when_accepted(
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
    assert [task["task_name"] for task in review["tasks"]] == PROPOSED
    assert [(task["state"], task["usable"]) for task in review["tasks"]] == [
        ("succeeded", True),
        ("failed", False),
        ("rejected", False),
        ("outcome_unknown", False),
        ("succeeded", False),
        ("succeeded", True),
    ]
    assert (
        review["tasks"][2]["why"] is not None
        and "task.toml" in (review["tasks"][2]["why"])
    )
    assert review["tasks"][4]["build_id"] is not None
    assert review["tasks"][4]["why"] is None
    assert [member["task_name"] for member in review["members"]] == [
        QUALIFIES,
        ALSO_QUALIFIES,
    ]
    assert review["version"] == 1 and review["previous"] is None
    assert [warning["id"] for warning in envelope["warnings"]] == [
        "forge_few_tasks",
        "forge_few_held_out",
    ]
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
    for name in PROPOSED:
        assert name in result.output
    assert "built, but did not qualify" in result.output
    assert "outcome unknown" in result.output
    assert "Accept these tasks as the collection?" in result.output
    assert "Only 2 tasks are in this collection" in result.output
    assert "at least 3 repetitions per task" in " ".join(result.output.split())
    accepted = read_collection_status(paths_from_root(home), collection_id)
    assert accepted.state == "accepted" and accepted.acceptance is not None
    assert accepted.acceptance.answered_with == "prompt"
    assert accepted.acceptance.collection_digest == accepted.record.collection_digest

    code, verified = invoke(home, "verify", collection_id)
    _, collected = invoke(home, "status", construction_id)

    assert code == 0, verified
    assert ["forge", "collect"] not in [
        action["prepared_arguments"]["command"] for action in collected["next_actions"]
    ]
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
    collection_id = collect(home, retry, "--task", QUALIFIES, "--task", ALSO_QUALIFIES)[
        "facts"
    ]["collection_id"]
    other = collect(home, retry)["facts"]["record"]["review"]
    assert invoke(home, "accept", collection_id, "--yes")[0] == 0
    # Someone adds a qualified task to the accepted collection and makes every
    # digest in the record agree again; the acceptance still names the old one.
    path = paths.forge_collection_dir(collection_id) / "collection.json"
    record = json.loads(path.read_bytes())
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
    creator = FakeCreator(
        calls={name: FakePlanner(timed_out=True) for name in PROPOSED}
    )
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
        ALSO_QUALIFIES,
    ]
    [warning] = envelope["warnings"]
    assert warning["id"] == "forge_few_held_out"
    assert "at least 2 repetitions per task" in warning["text"]
    assert invoke(home, "verify", v1)[0] == 0


# ---------------------------------------------------------------------------
# A baseline on the accepted collection
# ---------------------------------------------------------------------------


def accepted(home: Path, proposal_id: str, profiles: Path) -> str:
    """An accepted collection of the two tasks that qualified, one in each part."""
    construction_id = construct(home, proposal_id, profiles, ae5_creator())
    collection_id: str = collect(home, construction_id)["facts"]["collection_id"]
    assert invoke(home, "accept", collection_id, "--yes")[0] == 0
    return collection_id


def baseline(
    home: Path,
    collection_id: str,
    *,
    repetitions: int = 1,
    task_ids: list[str] | None = None,
) -> ForgeRunSpec:
    return declare_run_spec(
        paths_from_root(home),
        arm=ForgeArm.BASELINE,
        collection_id=collection_id,
        task_ids=task_ids,
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
    attempts = status.record.attempts
    gradings = [call for call in docker.calls if call[-1] == "bash /tests/test.sh"]
    assert len(attempts) == len(hermes.launches) == len(gradings) == 2
    for attempt, launch, grading in zip(
        attempts, hermes.launches, gradings, strict=True
    ):
        assert attempt.outcome is ForgeAttemptOutcome.GRADED
        assert attempt.reward == 1.0 and attempt.patch_digest is None
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
        kept = attempt_dir / "outputs" / "files" / "result.txt"
        assert kept.read_text() == "5\n"
        assert (workspace / "left-by-tests.txt").is_file()
        written_config = launch["config"]
        assert isinstance(written_config, bytes)
        config = json.loads(written_config)
        assert config["terminal"]["docker_volumes"] == [f"{workspace}:/app"]
        assert config["terminal"]["cwd"] == "/app"
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
    """AE8: the Source Skill's own bytes as the candidate keep both roles."""
    collection_id = accepted(home, proposal_id, profiles)
    paths = paths_from_root(home)
    skill = tmp_path / "branch-code"
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
    assert (record.wins, record.losses) == (2, 0)
    source, candidate = record.source_skill, record.candidate_skill
    assert source is not None and source.name == candidate.name == "branch-code"
    assert source.digest == candidate.digest
    assert record.baseline_skill is None
    page = Path(status.report_path).read_text(encoding="utf-8")
    assert f"<title>branch-code on collection {collection_id}</title>" in page
    assert "Evaluation on Skill-derived tasks" in page
    assert f"<dt>Tasks written from</dt><dd>branch-code ({source.digest})" in page
    assert f"<dt>Candidate Skill</dt><dd>branch-code ({candidate.digest})" in page
    assert "<dt>Baseline Skill</dt><dd>none</dd>" in page
    assert "a win here is not evidence that Skills help in general" in page
    assert f"{collection_id}, version 1" in page
    assert "complete these tasks, which were written from a Skill?" in page
    assert "1 added, 0 changed, 0 deleted in <code>/app</code>" in page
    assert "outputs/manifest.json" in page
    assert "Repository" not in page and "patch" not in page.lower()


#: One line of the task's reference solution, and one of its tests.
SOLUTION_LINE = (
    "python3 -c \"print(sum(map(int, open('/app/amounts.txt'))))\" > /app/result.txt"
)
TEST_LINE = 'if [ "$(cat /app/result.txt 2>/dev/null)" = 5 ]; then'


def test_skill_v1_to_v2_on_the_collection_keeps_every_role_and_is_revised_there(
    tmp_path: Path,
    home: Path,
    proposal_id: str,
    profiles: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R19, R36: v1 is the Source Skill's own bytes; v2 is measured against it.

    The comparison is then revised on the same collection: the reviser sees
    the tasks' instructions with their sandbox paths, never the reference
    solutions or tests, and the revised Skill is screened against both.
    """
    collection_id = accepted(home, proposal_id, profiles)
    paths = paths_from_root(home)
    v1 = tmp_path / "branch-code"
    v2 = write_skill(tmp_path / "v2", name="branch-code", body="Sum, then write.")
    hermes = FakeHermes(
        leaves=lambda directory: (directory / "result.txt").write_text(
            "5\n", encoding="utf-8"
        )
    )

    def run(arm: ForgeArm, skill_root: Path, reward: float) -> str:
        spec = declare_run_spec(
            paths,
            arm=arm,
            collection_id=collection_id,
            task_ids=None,
            skill_root=skill_root,
            provider="openai-codex",
            model_id="gpt-5.6-sol",
            reasoning=None,
            repetitions=3,
        )
        runner = ForgeRunner(
            paths, FakeDocker(reward=reward), launch=hermes, profiles_root=profiles
        )
        return runner.run(spec, skill_root).run_id

    baseline_id = run(ForgeArm.BASELINE, v1, 0.0)
    candidate_id = run(ForgeArm.CANDIDATE, v2, 1.0)

    status = compare_runs(paths, baseline_id, candidate_id)

    record = status.record
    source, earlier, later = (
        record.source_skill,
        record.baseline_skill,
        record.candidate_skill,
    )
    assert source is not None and earlier is not None
    assert source.digest == earlier.digest != later.digest
    assert record.verdict is ForgeVerdict.IMPROVED
    assert record.summary.startswith(
        "Improved on the baseline Skill. Over 6 graded pairs, the candidate Skill "
        "won 6, lost 0 and tied 0 against the baseline Skill"
    )
    page = Path(status.report_path).read_text(encoding="utf-8")
    assert "Evaluation on Skill-derived tasks" in page
    for role, skill in (
        ("Tasks written from", source),
        ("Baseline Skill", earlier),
        ("Candidate Skill", later),
    ):
        assert f"<dt>{role}</dt><dd>branch-code ({skill.digest})</dd>" in page
    assert "written from a Skill, more than the Skill <strong>branch-code" in page
    assert "Each arm had its own Skill preloaded" in page
    assert "The candidate Skill lost no graded pair." in page

    context = build_forge_improvement_context(paths, status.comparison_id)

    assert isinstance(context.tasks_from, ForgeImprovementCollection)
    assert (context.tasks_from.collection_id, context.tasks_from.version) == (
        collection_id,
        1,
    )
    assert "sum /app/amounts.txt" in context.examples[0].public_prompt
    serialized = context.model_dump_json()
    assert SOLUTION_LINE not in serialized and TEST_LINE not in serialized
    assert "the reference solutions of any task" in context.prohibited_material

    v3 = write_skill(
        tmp_path / "v3", name="branch-code", body=f"{SOLUTION_LINE}\n{TEST_LINE}"
    )
    revision = prepare_revision(
        paths, comparison_id=status.comparison_id, skill_root=v3, label=None
    )

    assert revision.record.tasks_from == record.tasks_from
    members = read_collection_status(paths, collection_id).record.review.members
    assert sorted(
        (f.task_id, f.material, f.excerpt) for f in revision.record.screening
    ) == sorted(
        (member.task_id, material, excerpt)
        for member in members
        for material, excerpt in (
            ("reference_solution", SOLUTION_LINE),
            ("tests", TEST_LINE),
        )
    )
    monkeypatch.setattr(
        "techtree.cli.commands.uplift.ForgeRunner",
        lambda paths, run: ForgeRunner(
            paths, FakeDocker(reward=1.0), launch=hermes, profiles_root=profiles
        ),
    )
    result = CliRunner().invoke(
        create_app(),
        [
            *("--home", str(home), "--json", "uplift", "start", "--yes"),
            *("--reviewed-on", "host-agent", revision.revision_id),
        ],
    )
    assert result.exit_code == 0, result.stdout
    measured = json.loads(result.stdout)["facts"]["revision"]
    assert measured["state"] == "measured"
    assert (
        "the revised Skill contains material from held-out tasks"
        in (measured["verdict"])
    )
    revised = shutil.copytree(v3, tmp_path / "revised" / "branch-code")
    _, looked = invoke(
        home, "inspect-skill", str(revised), "--derived-from", revision.revision_id
    )
    assert looked["facts"]["record"]["lineage"] == {
        "kind": "revision",
        "parent_id": revision.revision_id,
        "parent_digest": revision.record.skill.root_digest,
        "root_digest": read_collection_status(
            paths, collection_id
        ).record.review.line_digest,
    }

    # Paths in the task's own sandbox reach the reviser; a home folder does not.
    [member] = [member for member in members if member.part == "study"]
    task_dir = paths.forge_build_dir(member.build_id) / "tasks" / member.task_id
    (task_dir / "instruction.md").write_text(
        "Read /Users/someone/notes.txt first.\n", encoding="utf-8"
    )
    with pytest.raises(ValidationError) as refused:
        build_forge_improvement_context(paths, status.comparison_id)
    assert refused.value.code == "improvement_context_forbidden_material"


def test_runs_on_two_versions_of_a_collection_are_not_compared(
    home: Path, proposal_id: str, profiles: Path, tmp_path: Path
) -> None:
    """T13: the tasks a comparison pairs are one version's members, never two."""
    first = construct(home, proposal_id, profiles, ae5_creator())
    v1 = collect(home, first)["facts"]["collection_id"]
    assert invoke(home, "accept", v1, "--yes")[0] == 0
    retry = construct(home, proposal_id, profiles, FakeCreator(), retry_of=first)
    v2 = collect(home, retry, "--previous", v1)["facts"]["collection_id"]
    assert invoke(home, "accept", v2, "--yes")[0] == 0
    paths = paths_from_root(home)
    candidate = declare_run_spec(
        paths,
        arm=ForgeArm.CANDIDATE,
        collection_id=v2,
        task_ids=[
            member.task_id
            for member in read_collection_status(paths, v1).record.review.members
        ],
        skill_root=write_skill(tmp_path / "skills"),
        provider="openai-codex",
        model_id="gpt-5.6-sol",
        reasoning=None,
        repetitions=1,
    )

    comparison = compare_run_specs(baseline(home, v1), candidate)

    with pytest.raises(VerificationError) as refused:
        assert_comparable_run_specs(comparison)
    assert refused.value.code == "forge_comparison_invalid"
    assert "/tasks_from/collection_id differs between the arms" in (
        comparison.violations
    )


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
    task = read_collection_status(paths_from_root(home), collection_id).record.review
    declared = baseline(
        home, collection_id, repetitions=2, task_ids=[task.members[0].task_id]
    )
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
    members = read_collection_status(paths, collection_id).record.review.members
    builds = [read_build_status(paths, member.build_id) for member in members]
    build = builds[0]
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
    manifests = [
        manifest
        for member_build in builds
        if member_build.build is not None
        for manifest in member_build.build.task_set.tasks
    ]
    assert len(manifests) == 2
    files = sorted(path for path in moved.rglob("*") if path.is_file())
    assert [str(path.relative_to(moved)) for path in files] == sorted(
        [
            "README.md",
            "export.json",
            *(
                f"tasks/{manifest.task_id}/{entry.path}"
                for manifest in manifests
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
    readme = (moved / "README.md").read_text(encoding="utf-8")
    assert {member.claim for member in members} == {"C1"}
    assert "- C1: " in readme and "  - What shows it: " in readme
    assert "C2" not in readme


def test_a_changed_or_added_file_in_an_export_is_refused_by_name(
    home: Path, proposal_id: str, profiles: Path, tmp_path: Path
) -> None:
    collection_id = accepted(home, proposal_id, profiles)
    export = tmp_path / "export"
    assert invoke(home, "export", collection_id, "--to", str(export))[0] == 0
    task = min((export / "tasks").iterdir())
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


# ---------------------------------------------------------------------------
# Held-out tasks
# ---------------------------------------------------------------------------


def test_the_held_out_tasks_follow_from_the_tasks_alone_whatever_their_order() -> None:
    """Invariant (a): deterministic, independent of order, a task in each part."""
    proposal = "sha256:" + hashlib.sha256(b"proposal").hexdigest()
    for size in range(2, 9):
        members = [
            (f"task-{index}", "sha256:" + hashlib.sha256(bytes([index])).hexdigest())
            for index in range(size)
        ]
        parts = dict(zip(members, collection_parts(proposal, members, []), strict=True))

        assert list(parts.values()).count("held_out") == size // 2
        assert set(parts.values()) == {"study", "held_out"}
        for reordered in (members[::-1], members[1:] + members[:1]):
            assert collection_parts(proposal, reordered, []) == [
                parts[member] for member in reordered
            ]


def test_a_collection_of_one_task_is_refused(
    home: Path, proposal_id: str, profiles: Path
) -> None:
    """Invariant (d): a collection needs a task in each part."""
    construction_id = construct(home, proposal_id, profiles, ae5_creator())

    code, envelope = invoke(home, "collect", construction_id, "--task", QUALIFIES)

    assert code != 0
    assert envelope["error"]["code"] == "forge_collection_too_few"
    assert (
        f"{ALSO_QUALIFIES} also qualified but was left out by --task"
        in (envelope["error"]["message"])
    )


def test_the_same_task_twice_under_two_names_is_refused(
    home: Path, proposal_id: str, profiles: Path
) -> None:
    """One task written twice could be studied under one name and held out
    under the other."""
    twice = FakeCreator(
        calls={ALSO_QUALIFIES: FakePlanner(answer=created_package(QUALIFIES))}
    )
    construction_id = construct(home, proposal_id, profiles, twice)

    code, envelope = invoke(home, "collect", construction_id)

    assert code != 0
    assert envelope["error"]["code"] == "forge_collection_duplicate_task"
    assert (
        f"{QUALIFIES} and {ALSO_QUALIFIES} have exactly the same files"
        in (envelope["error"]["message"])
    )


def test_the_improving_agent_never_sees_a_held_out_task(
    tmp_path: Path,
    home: Path,
    proposal_id: str,
    profiles: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invariant (b): no held-out id, name or instruction, though its runs did,
    in the context or in preparing, reviewing and measuring a revision, even
    one that copies a held-out task's instruction; runs that leave out tasks
    of either part give no context and no revision, and naming a task that
    is not in the collection lists none that are."""
    collection_id = accepted(home, proposal_id, profiles)
    paths = paths_from_root(home)
    members = read_collection_status(paths, collection_id).record.review.members
    [studied] = [member for member in members if member.part == "study"]
    [held_out] = [member for member in members if member.part == "held_out"]
    instruction = (
        paths.forge_build_dir(held_out.build_id)
        / "tasks"
        / held_out.task_id
        / "instruction.md"
    ).read_text(encoding="utf-8")
    hermes = FakeHermes(
        leaves=lambda directory: (directory / "result.txt").write_text(
            "5\n", encoding="utf-8"
        )
    )

    def run(
        arm: ForgeArm,
        skill_root: Path,
        reward: float,
        task_ids: list[str] | None = None,
    ) -> str:
        spec = declare_run_spec(
            paths,
            arm=arm,
            collection_id=collection_id,
            task_ids=task_ids,
            skill_root=skill_root,
            provider="openai-codex",
            model_id="gpt-5.6-sol",
            reasoning=None,
            repetitions=1,
        )
        runner = ForgeRunner(
            paths, FakeDocker(reward=reward), launch=hermes, profiles_root=profiles
        )
        return runner.run(spec, skill_root).run_id

    v2 = write_skill(tmp_path / "v2", name="branch-code", body="Sum, then write.")
    comparison = compare_runs(
        paths,
        run(ForgeArm.BASELINE, tmp_path / "branch-code", 0.0),
        run(ForgeArm.CANDIDATE, v2, 1.0),
    )
    assert comparison.record.held_out is not None
    assert comparison.record.held_out.task_ids == [held_out.task_id]

    shown = [
        CliRunner().invoke(
            create_app(),
            [
                "--home",
                str(home),
                *flags,
                "uplift",
                "context",
                comparison.comparison_id,
            ],
        )
        for flags in ([], ["--json"])
    ]
    written = (Path(comparison.path) / "improvement" / "context.json").read_text(
        encoding="utf-8"
    )

    for text in (*(result.stdout for result in shown), written):
        assert studied.task_id in text
        for hidden in (held_out.task_id, held_out.task_name, instruction.strip()):
            assert hidden not in text

    v3 = write_skill(tmp_path / "v3", name="branch-code", body=instruction.strip())
    monkeypatch.setattr(
        "techtree.cli.commands.uplift.ForgeRunner",
        lambda paths, run: ForgeRunner(
            paths, FakeDocker(reward=1.0), launch=hermes, profiles_root=profiles
        ),
    )

    def uplift(*arguments: str) -> str:
        result = CliRunner().invoke(
            create_app(), ["--home", str(home), *arguments], terminal_width=500
        )
        assert result.exit_code == 0, result.stdout
        return result.stdout

    revisions: set[str] = set()
    for flags in ([], ["--json"]):
        prepared = uplift(
            *flags,
            *("uplift", "prepare", "--from-run", comparison.comparison_id),
            *("--candidate-skill", str(v3)),
        )
        [revision] = {path.name for path in paths.forge_revisions_dir.iterdir()} - (
            revisions
        )
        revisions.add(revision)
        screened = read_revision_status(paths, revision).record.screening
        assert held_out.task_id in {finding.task_id for finding in screened}
        reviewed = uplift("--no-input", *flags, "uplift", "start", revision)
        started = uplift(
            *flags,
            *("uplift", "start", "--yes", "--reviewed-on", "host-agent", revision),
        )
        for text in (prepared, reviewed, started):
            assert studied.task_id in text
            for hidden in (held_out.task_id, held_out.task_name, held_out.build_id):
                assert hidden not in text

    for part in (studied, held_out):
        partial = compare_runs(
            paths,
            run(ForgeArm.BASELINE, tmp_path / "branch-code", 0.0, [part.task_id]),
            run(ForgeArm.CANDIDATE, v2, 1.0, [part.task_id]),
        )
        for arguments in (
            ["uplift", "context", partial.comparison_id],
            [
                *("uplift", "prepare", "--from-run", partial.comparison_id),
                *("--candidate-skill", str(v3)),
            ],
        ):
            refused = CliRunner().invoke(
                create_app(), ["--home", str(home), "--json", *arguments]
            )
            assert refused.exit_code != 0
            assert '"forge_revision_partial_collection"' in refused.stdout
            for hidden in (held_out.task_id, held_out.task_name, held_out.build_id):
                assert hidden not in refused.stdout
        assert not (Path(partial.path) / "improvement").exists()
    assert {path.name for path in paths.forge_revisions_dir.iterdir()} == revisions
    with pytest.raises(ValidationError) as unknown:
        baseline(home, collection_id, task_ids=["local__other-000000000002"])
    said = unknown.value.message + json.dumps(unknown.value.details)
    assert unknown.value.code == "forge_task_not_qualified"
    assert held_out.task_id not in said and studied.task_id not in said


#: The line the tasks' reference solution runs, which only a Skill may hold
#: that already had it.
SOLVE_LINE = (
    "python3 -c \"print(sum(map(int, open('/app/amounts.txt'))))\" > /app/result.txt"
)


class RewardByTask(FakeDocker):
    """Docker whose tests grade each task by the reward named for it."""

    def __init__(self, rewards: dict[str, float]) -> None:
        super().__init__()
        self.rewards = rewards

    def __call__(
        self, argv: Sequence[str], timeout: float
    ) -> subprocess.CompletedProcess[str]:
        command = list(argv)
        if command[-1] == "bash /tests/test.sh":
            mounted = next(part for part in command if part.endswith(":/app"))
            [self.reward] = [
                reward
                for task_id, reward in self.rewards.items()
                if f"/tasks/{task_id}/" in mounted
            ]
        return super().__call__(argv, timeout)


def test_a_revision_is_judged_on_its_held_out_tasks_alone(
    tmp_path: Path, home: Path, proposal_id: str, profiles: Path
) -> None:
    """Invariant (c): the verdict follows the held-out pairs, whatever the rest
    do, and needs as many graded pairs as every other verdict; a line the
    revision kept from the Skill it revised, or had from a task it could
    see, does not stop it being judged."""
    shared = "Each line of amounts.txt holds one whole number, nothing else."

    def with_notes(name: str) -> FakePlanner:
        answer = json.loads(created_package(name))
        answer["files"].append(
            {
                "path": "environment/notes.txt",
                "text": shared + "\n",
                "executable": False,
            }
        )
        return FakePlanner(answer=json.dumps(answer).encode())

    creator = ae5_creator()
    creator.calls.update(
        {name: with_notes(name) for name in (QUALIFIES, ALSO_QUALIFIES)}
    )
    collection_id = collect(home, construct(home, proposal_id, profiles, creator))[
        "facts"
    ]["collection_id"]
    assert invoke(home, "accept", collection_id, "--yes")[0] == 0
    paths = paths_from_root(home)
    parts = read_collection_status(paths, collection_id).record.review.parts()
    [studied] = [task_id for task_id, part in parts.items() if part == "study"]
    [held_out] = [task_id for task_id, part in parts.items() if part == "held_out"]
    hermes = FakeHermes(
        leaves=lambda directory: (directory / "result.txt").write_text(
            "5\n", encoding="utf-8"
        )
    )

    def runner(docker: FakeDocker) -> ForgeRunner:
        return ForgeRunner(paths, docker, launch=hermes, profiles_root=profiles)

    def run(arm: ForgeArm, skill_root: Path, repetitions: int) -> str:
        spec = declare_run_spec(
            paths,
            arm=arm,
            collection_id=collection_id,
            task_ids=None,
            skill_root=skill_root,
            provider="openai-codex",
            model_id="gpt-5.6-sol",
            reasoning=None,
            repetitions=repetitions,
        )
        return runner(FakeDocker(reward=0.0)).run(spec, skill_root).run_id

    v2 = write_skill(
        tmp_path / "v2", name="branch-code", body=f"Sum, then write.\n\n{SOLVE_LINE}"
    )

    def compared(repetitions: int) -> str:
        return compare_runs(
            paths,
            run(ForgeArm.BASELINE, tmp_path / "branch-code", repetitions),
            run(ForgeArm.CANDIDATE, v2, repetitions),
        ).comparison_id

    judged = compared(3)
    moved = "branch-code {} branch-code"
    cases = [
        (judged, {studied: 1.0, held_out: 0.0}, moved.format("matched"), "improved on"),
        (judged, {studied: 0.0, held_out: 1.0}, moved.format("improved on"), "matched"),
        (compared(1), {studied: 0.0, held_out: 1.0}, "is inconclusive", "inconclusive"),
    ]

    for index, (comparison_id, rewards, verdict, study_verdict) in enumerate(cases):
        v3 = write_skill(
            tmp_path / f"v3-{index}",
            name="branch-code",
            body=f"Add them, then write.\n\n{SOLVE_LINE}\n\n{shared}",
        )
        revision = prepare_revision(
            paths, comparison_id=comparison_id, skill_root=v3, label=None
        )
        assert revision.record.screening == []

        record = measure_revision(
            paths, revision.revision_id, runner(RewardByTask(rewards))
        ).revision.record

        assert record.verdict is not None and record.study_verdict is not None
        assert record.verdict.startswith("On the 1 held-out task, which the agent")
        assert verdict in record.verdict
        assert study_verdict in record.study_verdict


def test_a_task_keeps_its_part_in_every_later_version(
    tmp_path: Path, home: Path, proposal_id: str, profiles: Path
) -> None:
    """Invariant: a task's part, once given, holds as tasks are added,
    removed, added again and built again, and a new first version of the
    same Skill's tasks, a version of an older one, and a second version of
    the same one are refused; a Skill derived from it stays in its line."""
    first = construct(home, proposal_id, profiles, ae5_creator())
    retry = construct(home, proposal_id, profiles, FakeCreator(), retry_of=first)
    paths = paths_from_root(home)

    def accepted_version(construction_id: str, *arguments: str) -> dict[str, str]:
        collection_id = collect(home, construction_id, *arguments)["facts"][
            "collection_id"
        ]
        assert invoke(home, "accept", collection_id, "--yes")[0] == 0
        versions.append(collection_id)
        review = read_collection_status(paths, collection_id).record.review
        return {member.task_name: member.part for member in review.members}

    versions: list[str] = []
    v1 = accepted_version(first)
    v2 = accepted_version(retry, "--previous", versions[-1])
    [dropped] = [name for name, part in v1.items() if part == "study"]
    kept = [arg for name in v2 if name != dropped for arg in ("--task", name)]
    v3 = accepted_version(retry, *kept, "--previous", versions[-1])
    v4 = accepted_version(retry, "--previous", versions[-1])
    reworded = FakeCreator(
        calls={
            name: FakePlanner(
                answer=created_package(name).replace(b", sum ", b", add up ")
            )
            for name in PROPOSED
        }
    )
    rebuilt = construct(home, proposal_id, profiles, reworded)
    _, fresh = invoke(home, "collect", rebuilt)
    _, older = invoke(home, "collect", rebuilt, "--previous", versions[1])
    sibling = collect(home, rebuilt, "--previous", versions[-1])["facts"][
        "collection_id"
    ]
    v5 = accepted_version(rebuilt, "--previous", versions[-1])
    _, second = invoke(home, "accept", sibling, "--yes")
    reduced = tmp_path / "reduced" / "branch-code"
    reduced.mkdir(parents=True)
    (reduced / "SKILL.md").write_text(SKILL + "2. Keep it short.\n", encoding="utf-8")
    original = read_collection_status(paths, versions[0]).record.review.source_id
    _, looked = invoke(home, "inspect-skill", str(reduced), "--derived-from", original)
    derived = construct(
        home,
        propose(tmp_path, home, profiles, looked["facts"]["source_id"]),
        profiles,
        FakeCreator(),
    )
    _, fresh_derived = invoke(home, "collect", derived)
    v6 = accepted_version(derived, "--previous", versions[-1])

    assert len(v1) < len(v2) and dropped not in v3 and dropped in v4
    assert fresh["error"]["code"] == "forge_collection_has_versions"
    assert older["error"]["code"] == "forge_collection_not_latest"
    assert second["error"]["code"] == "forge_collection_not_latest"
    for refused, latest in ((fresh, versions[3]), (older, versions[3])):
        assert f"--previous {latest}" in refused["error"]["message"]
    assert f"--previous {versions[4]}" in second["error"]["message"]
    assert fresh_derived["error"]["code"] == "forge_collection_has_versions"
    assert f"--previous {versions[4]}" in fresh_derived["error"]["message"]
    assert read_collection_status(paths, sibling).acceptance is None
    fingerprints = [
        {
            member.fingerprint
            for member in read_collection_status(paths, version).record.review.members
        }
        for version in versions
    ]
    assert not fingerprints[4] & set().union(*fingerprints[:4])
    given: dict[str, str] = {}
    for version in (v1, v2, v3, v4, v5, v6):
        for name, part in version.items():
            assert given.setdefault(name, part) == part, name

    unreadable = paths.forge_collections_dir / ("forgecol_" + "0" * 32)
    unreadable.mkdir()
    (unreadable / "collection.json").write_text("{}", encoding="utf-8")
    for arguments in (("status", derived), ("collect", derived)):
        _, refused = invoke(home, *arguments)
        assert refused["error"]["code"] == "forge_collection_unreadable"
        assert str(unreadable) in refused["error"]["message"]
