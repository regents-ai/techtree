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
out on the held-out tasks alone. An export's own README commands, followed
in a fresh home with only the export and the Skill, import it, run both arms
and compare them on the same collection, tasks and parts as where it was
accepted (item 19). Checking an export shows it agrees with its own records,
so its README, verify-export and import show the collection's fingerprint for
its reader to match; a changed export, one whose tasks name another Skill than
its collection, one built for another Docker platform, or one whose task does
not qualify on the importing computer, leaves nothing behind, and an import
that fails never removes what another made. A person's corrected copy of a
built task is admitted and qualified like a created one, as a new build, and
recorded with what it replaced and which files changed, the original build
left as it was; collecting takes each task's newest correction and marks on
every task whether a person corrected it, and a folder that is unchanged,
misnamed, refused at admission or does not qualify records nothing. The
creator, Docker and Hermes are the stand-ins of the construction and run
tests; no model is called.
"""

from __future__ import annotations

import hashlib
import json
import shlex
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
from techtree.errors import (
    NotFoundError,
    RunError,
    TechtreeError,
    ValidationError,
    VerificationError,
)
from techtree.forge.capture import MANIFEST_FILENAME
from techtree.forge.collection import read_collection_status
from techtree.forge.comparability import (
    assert_comparable_run_specs,
    compare_run_specs,
)
from techtree.forge.compare import compare_runs, read_comparison_status
from techtree.forge.construction import (
    correct_task,
    read_construction_status,
    start_construction,
)
from techtree.forge.content import verify_task_set
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
    ForgeConstructionStatus,
    ForgeConstructionTaskStatus,
    ForgeEvidence,
    ForgeExport,
    ForgeOutputLimits,
    ForgeOutputManifest,
    ForgeRunSpec,
    ForgeSkillSource,
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
from techtree.forge.service import (
    ForgeService,
    host_docker_platform,
    read_build_status,
)
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
# A person's correction of a task
# ---------------------------------------------------------------------------


def correct(
    home: Path, construction_id: str, task_name: str, folder: Path, *, qualifies: bool
) -> ForgeConstructionStatus:
    """Correct a task, its package graded as qualifying or, when not, by tests
    that pass when nothing is done."""
    paths = paths_from_root(home)
    run = (
        FakeDocker(reward=0.0, reference_reward=1.0)
        if qualifies
        else FakeDocker(reward=1.0)
    )
    return correct_task(
        paths,
        construction_id,
        task_name,
        folder,
        qualify=lambda task_dir, source_skill, source_digest: ForgeService(
            paths, run, Path("/fake/uv")
        ).import_skill(
            task_dir=task_dir, source_skill=source_skill, source_digest=source_digest
        ),
    )


def copy_out(home: Path, build_id: str, destination: Path) -> Path:
    """Copy a built package out of its build, as a person does to edit it."""
    [package] = Path(
        read_build_status(paths_from_root(home), build_id).tasks_path
    ).iterdir()
    destination.mkdir()
    return Path(shutil.copytree(package, destination / package.name))


def task_status(
    home: Path, construction_id: str, task_name: str
) -> ForgeConstructionTaskStatus:
    status = read_construction_status(paths_from_root(home), construction_id)
    [task] = [task for task in status.tasks if task.task_name == task_name]
    return task


def append(path: Path, text: str) -> None:
    path.write_text(path.read_text(encoding="utf-8") + text, encoding="utf-8")


def test_a_corrected_task_is_checked_as_a_new_build_and_recorded(
    home: Path, proposal_id: str, profiles: Path, tmp_path: Path
) -> None:
    paths = paths_from_root(home)
    construction_id = construct(home, proposal_id, profiles, ae5_creator())
    created = task_status(home, construction_id, QUALIFIES).package
    assert created is not None
    original = read_build_status(paths, created.build_id)
    assert original.build is not None
    folder = copy_out(home, created.build_id, tmp_path / "edit")
    append(folder / "tests" / "test.sh", "# read and checked by hand\n")
    (folder / "tests" / "helper.py").write_text("TOTAL = 5\n", encoding="utf-8")

    status = correct(home, construction_id, QUALIFIES, folder, qualifies=True)

    [task] = [task for task in status.tasks if task.task_name == QUALIFIES]
    [correction] = task.corrections
    built = read_build_status(paths, correction.build_id)
    assert built.build is not None and built.usable_tasks == 1
    assert correction.build_id != created.build_id
    assert correction.replaces == created.build_id
    assert correction.replaced_digest == original.build.task_set.tasks[0].content_digest
    assert correction.content_digest == built.build.task_set.tasks[0].content_digest
    assert [(change.path, change.change) for change in correction.changes] == [
        ("tests/helper.py", "added"),
        ("tests/test.sh", "modified"),
    ]
    # The original build is left exactly as it was built.
    verify_task_set(Path(original.tasks_path), original.build.task_set)
    assert task.package == created
    code, shown = invoke(home, "status", construction_id)
    assert code == 0
    assert [
        correction["build_id"]
        for correction in shown["facts"]["tasks"][0]["corrections"]
    ] == [correction.build_id]
    printed = CliRunner().invoke(
        create_app(), ["--home", str(home), "forge", "status", construction_id]
    )
    words = " ".join(printed.output.split())
    assert (
        f"{QUALIFIES}: corrected by a person, usable, checked as build "
        f"{correction.build_id}"
    ) in words
    assert "tests/helper.py added, tests/test.sh modified" in words


def test_collect_takes_each_tasks_newest_correction_and_says_so(
    home: Path, proposal_id: str, profiles: Path, tmp_path: Path
) -> None:
    construction_id = construct(home, proposal_id, profiles, ae5_creator())
    created = task_status(home, construction_id, QUALIFIES).package
    assert created is not None
    first_dir = copy_out(home, created.build_id, tmp_path / "first")
    (first_dir / "tests" / "helper.py").write_text("TOTAL = 5\n", encoding="utf-8")
    correct(home, construction_id, QUALIFIES, first_dir, qualifies=True)
    [first] = task_status(home, construction_id, QUALIFIES).corrections
    second_dir = copy_out(home, first.build_id, tmp_path / "second")
    (second_dir / "tests" / "helper.py").unlink()
    append(second_dir / "instruction.md", "Write only the number.\n")
    correct(home, construction_id, QUALIFIES, second_dir, qualifies=True)
    _, second = task_status(home, construction_id, QUALIFIES).corrections
    # A built package that did not qualify is rescued the same way.
    unqualified = task_status(home, construction_id, DOES_NOT_QUALIFY).package
    assert unqualified is not None and unqualified.usable_tasks == 0
    rescue_dir = copy_out(home, unqualified.build_id, tmp_path / "rescue")
    append(rescue_dir / "tests" / "test.sh", "# fails when nothing is done\n")
    correct(home, construction_id, DOES_NOT_QUALIFY, rescue_dir, qualifies=True)
    [rescue] = task_status(home, construction_id, DOES_NOT_QUALIFY).corrections
    also = task_status(home, construction_id, ALSO_QUALIFIES).package
    assert also is not None

    assert second.replaces == first.build_id
    assert second.replaced_digest == first.content_digest
    assert [(change.path, change.change) for change in second.changes] == [
        ("instruction.md", "modified"),
        ("tests/helper.py", "removed"),
    ]
    review = collect(home, construction_id)["facts"]["record"]["review"]
    tasks = {task["task_name"]: task for task in review["tasks"]}
    assert tasks[QUALIFIES]["build_id"] == second.build_id
    assert [c["build_id"] for c in tasks[QUALIFIES]["corrections"]] == [
        first.build_id,
        second.build_id,
    ]
    assert tasks[DOES_NOT_QUALIFY]["usable"] is True
    assert tasks[ALSO_QUALIFIES]["corrections"] == []
    assert {
        member["task_name"]: member["build_id"] for member in review["members"]
    } == {
        QUALIFIES: second.build_id,
        DOES_NOT_QUALIFY: rescue.build_id,
        ALSO_QUALIFIES: also.build_id,
    }

    collection_id = collect(home, construction_id)["facts"]["collection_id"]
    accepted = CliRunner().invoke(
        create_app(),
        ["--home", str(home), "forge", "accept", collection_id],
        input="y\n",
    )

    assert accepted.exit_code == 0, accepted.output
    words = " ".join(accepted.output.split())
    assert f"{QUALIFIES}: qualified; corrected by a person 2 times, last on" in words
    assert (
        f"{ALSO_QUALIFIES}: qualified, checked as build {also.build_id}; not "
        "corrected by a person"
    ) in words
    assert f"{FAILS}: failed" in words and "; not corrected by a person" in words
    assert (
        "The automatic checks show that each task's grader agrees with its own "
        "sample solutions, not that it accepts every correct answer, so read "
        "each task, and correct any with forge correct-task and collect again, "
        "before accepting."
    ) in words
    # A correction made after acceptance leaves the accepted collection as it was.
    third_dir = copy_out(home, second.build_id, tmp_path / "third")
    append(third_dir / "instruction.md", "Nothing else.\n")
    correct(home, construction_id, QUALIFIES, third_dir, qualifies=True)
    assert invoke(home, "verify", collection_id)[0] == 0

    export = tmp_path / "export"
    assert invoke(home, "export", collection_id, "--to", str(export))[0] == 0

    exported = ForgeExport.model_validate_json((export / "export.json").read_bytes())
    exported_tasks = {task.task_name: task for task in exported.collection.review.tasks}
    assert [c.build_id for c in exported_tasks[QUALIFIES].corrections] == [
        first.build_id,
        second.build_id,
    ]
    readme = (export / "README.md").read_text(encoding="utf-8").splitlines()
    [corrected_line] = [line for line in readme if f"the task {QUALIFIES}" in line]
    [plain_line] = [line for line in readme if f"the task {ALSO_QUALIFIES}" in line]
    assert "(corrected by a person)" in corrected_line
    assert "(corrected by a person)" not in plain_line


def test_a_task_the_creator_wrote_nothing_for_can_be_rescued(
    home: Path, proposal_id: str, profiles: Path, tmp_path: Path
) -> None:
    construction_id = construct(home, proposal_id, profiles, ae5_creator())
    failed = task_status(home, construction_id, FAILS)
    assert failed.state == "failed" and failed.package is None
    created = task_status(home, construction_id, QUALIFIES).package
    assert created is not None
    # The person writes the task from another one, under its own package name.
    copied = copy_out(home, created.build_id, tmp_path / "rescue")
    folder = copied.rename(copied.parent / failed.package_name)
    toml = folder / "task.toml"
    toml.write_text(
        toml.read_text(encoding="utf-8").replace(copied.name, failed.package_name),
        encoding="utf-8",
    )
    (folder / "instruction.md").write_text(
        f"For {FAILS}, sum /app/amounts.txt and write the integer to "
        "/app/result.txt.\n",
        encoding="utf-8",
    )

    status = correct(home, construction_id, FAILS, folder, qualifies=True)

    [task] = [task for task in status.tasks if task.task_name == FAILS]
    [correction] = task.corrections
    assert correction.replaces is None and correction.replaced_digest is None
    assert {change.change for change in correction.changes} == {"added"}
    assert "task.toml" in [change.path for change in correction.changes]
    review = collect(home, construction_id)["facts"]["record"]["review"]
    [rescued] = [task for task in review["tasks"] if task["task_name"] == FAILS]
    assert rescued["usable"] is True and rescued["why"] is not None
    assert FAILS in [member["task_name"] for member in review["members"]]
    # A retry builds only the tasks still without a usable package.
    code, retry = invoke(
        home,
        "construct",
        proposal_id,
        "--provider",
        "openai-codex",
        "--model",
        "gpt-5.6-sol",
        "--retry-of",
        construction_id,
    )
    assert code == 0, retry
    calls = retry["facts"]["record"]["review"]["disclosure"]["calls"]
    assert [call["task_name"] for call in calls] == [
        REJECTED,
        TIMES_OUT,
        DOES_NOT_QUALIFY,
    ]
    # A task that retry builds again is corrected there, not here.
    with pytest.raises(ValidationError) as retried:
        correct(home, construction_id, REJECTED, folder, qualifies=True)
    assert retried.value.code == "forge_correction_retried"


def test_a_correction_that_cannot_be_used_is_refused_and_records_nothing(
    home: Path, proposal_id: str, profiles: Path, tmp_path: Path
) -> None:
    paths = paths_from_root(home)
    construction_id = construct(home, proposal_id, profiles, ae5_creator())
    created = task_status(home, construction_id, QUALIFIES).package
    assert created is not None
    folder = copy_out(home, created.build_id, tmp_path / "edit")
    builds = sorted(paths.forge_builds_dir.iterdir())

    with pytest.raises(ValidationError) as unchanged:
        correct(home, construction_id, QUALIFIES, folder, qualifies=True)
    misnamed = Path(shutil.copytree(folder, tmp_path / "other" / "task_other_12345678"))
    _, wrong_name = invoke(
        home, "correct-task", construction_id, QUALIFIES, str(misnamed)
    )
    with pytest.raises(NotFoundError) as no_task:
        correct(home, construction_id, "branch-code-missing", folder, qualifies=True)
    _, prepared = invoke(
        home,
        "construct",
        proposal_id,
        "--provider",
        "openai-codex",
        "--model",
        "gpt-5.6-sol",
    )
    with pytest.raises(ValidationError) as not_ready:
        correct(
            home,
            prepared["facts"]["construction_id"],
            QUALIFIES,
            folder,
            qualifies=True,
        )

    assert unchanged.value.code == "forge_correction_unchanged"
    assert "a correction has to change something" in unchanged.value.message
    assert wrong_name["error"]["code"] == "forge_correction_wrong_name"
    assert no_task.value.code == "forge_correction_no_task"
    assert not_ready.value.code == "forge_correction_not_ready"
    assert sorted(paths.forge_builds_dir.iterdir()) == builds

    (folder / "tests" / ".notes").write_text("remember\n", encoding="utf-8")
    with pytest.raises(RunError) as hidden:
        correct(home, construction_id, QUALIFIES, folder, qualifies=True)
    (folder / "tests" / ".notes").unlink()
    append(folder / "tests" / "test.sh", "# edited\n")
    with pytest.raises(RunError) as unqualified:
        correct(home, construction_id, QUALIFIES, folder, qualifies=False)

    assert hidden.value.code == "forge_task_content_invalid"
    assert "hidden" in hidden.value.message
    assert unqualified.value.code == "forge_no_usable_tasks"
    for refused in (hidden.value, unqualified.value):
        assert "nothing was recorded" in refused.message
        assert refused.details["task_name"] == QUALIFIES
    assert task_status(home, construction_id, QUALIFIES).corrections == []
    assert not (paths.forge_construction_dir(construction_id) / "corrections").exists()


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
    changed = shutil.copytree(v3, tmp_path / "changed" / "branch-code")
    with (changed / "SKILL.md").open("a", encoding="utf-8") as skill_file:
        skill_file.write("Check twice.\n")
    _, other = invoke(
        home, "inspect-skill", str(changed), "--derived-from", revision.revision_id
    )
    assert other["error"]["code"] == "forge_source_not_revision"
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


def readme_commands(export: Path) -> list[list[str]]:
    """The commands an export's README lists in order, as argv."""
    readme = (export / "README.md").read_text(encoding="utf-8")
    block = readme.split("### The commands, in order\n\n```\n", 1)[1]
    return [shlex.split(line) for line in block.split("\n```", 1)[0].splitlines()]


def test_an_export_followed_by_its_readme_in_a_fresh_home_compares_as_the_original(
    home: Path,
    proposal_id: str,
    profiles: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Item 19: only the export folder and the Skill, and the README's commands
    exactly as printed, give a comparison on the same collection, the same
    tasks and the same parts as one made where the collection was accepted."""
    collection_id = accepted(home, proposal_id, profiles)
    skill = tmp_path / "branch-code"
    hermes = FakeHermes(
        leaves=lambda directory: (directory / "result.txt").write_text(
            "5\n", encoding="utf-8"
        )
    )
    rewards = iter([0.0, 1.0, 0.0, 1.0])
    monkeypatch.setattr(
        "techtree.cli.commands.forge.ForgeRunner",
        lambda paths, run: ForgeRunner(
            paths,
            FakeDocker(reward=next(rewards)),
            launch=hermes,
            profiles_root=profiles,
        ),
    )
    monkeypatch.setattr(
        "techtree.cli.commands.forge.run_command",
        FakeDocker(reward=0.0, reference_reward=1.0),
    )
    common = ["--collection", collection_id, "--provider", "openai-codex"]
    original_runs = [
        invoke(home, "run", "--arm", arm, *common, "--model", "gpt-5.6-sol", *extra)[1][
            "facts"
        ]["run_id"]
        for arm, extra in (
            ("baseline", ["--yes"]),
            ("candidate", ["--skill", str(skill), "--yes"]),
        )
    ]
    code, compared = invoke(home, "compare", *original_runs)
    assert code == 0, compared
    original = read_comparison_status(
        paths_from_root(home), compared["facts"]["comparison_id"]
    ).record
    export = tmp_path / "export"
    assert invoke(home, "export", collection_id, "--to", str(export))[0] == 0
    moved = tmp_path / "elsewhere"
    export.rename(moved)
    fresh = tmp_path / "fresh-home"
    fresh.mkdir()

    values = {
        "EXPORT_FOLDER": str(moved),
        "SKILL_FOLDER": str(skill),
        "PROVIDER": "openai-codex",
        "MODEL": "gpt-5.6-sol",
    }
    commands = readme_commands(moved)
    assert [argv[:3] for argv in commands] == [
        ["techtree", "forge", verb]
        for verb in (
            "verify-export",
            "import",
            "inspect-skill",
            "run",
            "run",
            "compare",
        )
    ]
    fingerprint = read_collection_status(
        paths_from_root(home), collection_id
    ).record.collection_digest
    readme = (moved / "README.md").read_text(encoding="utf-8")
    shown: dict[str, str] = {}
    for argv in commands:
        filled = [values.get(word, word) for word in argv[1:]]
        # A person answers yes where a run asks before it starts.
        code, envelope = invoke(fresh, *filled[1:], *(["--yes"] * (argv[2] == "run")))
        assert code == 0, (argv, envelope)
        shown[argv[2]] = json.dumps(envelope)
        if argv[2] == "run":
            arm = argv[argv.index("--arm") + 1]
            values[f"{arm.upper()}_RUN_ID"] = envelope["facts"]["run_id"]

    paths = paths_from_root(fresh)
    [comparison_dir] = paths.forge_comparisons_dir.iterdir()
    record = read_comparison_status(paths, comparison_dir.name).record
    imported = read_collection_status(paths, collection_id)
    assert imported.imported is not None
    assert (
        imported.record
        == read_collection_status(paths_from_root(home), collection_id).record
    )
    assert record.tasks_from == original.tasks_from
    assert [pair.task_id for pair in record.pairs] == [
        pair.task_id for pair in original.pairs
    ]
    assert record.study is not None and original.study is not None
    assert record.held_out is not None and original.held_out is not None
    assert record.study.task_ids == original.study.task_ids
    assert record.held_out.task_ids == original.held_out.task_ids
    assert (record.source_skill, record.candidate_skill) == (
        original.source_skill,
        original.candidate_skill,
    )
    assert (record.wins, record.losses) == (original.wins, original.losses) == (2, 0)
    # The reader can match the collection and the Skill against what the
    # sender gave, in full, at each step that shows them.
    assert fingerprint in readme
    assert fingerprint in shown["verify-export"] and fingerprint in shown["import"]
    skill_digest = imported.record.review.source_digest
    assert skill_digest in readme and skill_digest in shown["inspect-skill"]
    with pytest.raises(ValidationError) as refused:
        prepare_revision(
            paths, comparison_id=comparison_dir.name, skill_root=skill, label=None
        )
    assert refused.value.code == "forge_revision_imported"


def reseal(export: Path, forged: ForgeExport) -> None:
    """Write ``forged`` as the export's records, its collection and
    acceptance digests made to agree with its review again."""
    review = forged.collection.review
    record = forged.collection.model_copy(
        update={"collection_digest": digest_object(review)}
    )
    acceptance = forged.acceptance.model_copy(
        update={"collection_digest": record.collection_digest}
    )
    forged = forged.model_copy(update={"collection": record, "acceptance": acceptance})
    (export / "export.json").write_text(forged.model_dump_json(), encoding="utf-8")


def test_an_export_whose_tasks_name_another_skill_is_refused(
    home: Path, proposal_id: str, profiles: Path, tmp_path: Path
) -> None:
    """Each task's build and its own task.toml have to name the Skill the
    collection says the tasks were written from, even in records made to
    agree with each other again."""
    collection_id = accepted(home, proposal_id, profiles)
    export = tmp_path / "export"
    assert invoke(home, "export", collection_id, "--to", str(export))[0] == 0
    records = ForgeExport.model_validate_json((export / "export.json").read_bytes())
    other = "sha256:" + "ab" * 32
    first = records.tasks[0]
    assert isinstance(first.build.source, ForgeSkillSource)
    other_build = first.build.model_copy(
        update={
            "source": first.build.source.model_copy(
                update={"source_skill_digest": other}
            )
        }
    )
    review = records.collection.review
    for forged in (
        records.model_copy(
            update={
                "tasks": [
                    first.model_copy(update={"build": other_build}),
                    *records.tasks[1:],
                ]
            }
        ),
        records.model_copy(
            update={
                "collection": records.collection.model_copy(
                    update={
                        "review": review.model_copy(update={"source_name": "other"})
                    }
                )
            }
        ),
    ):
        reseal(export, forged)

        code, envelope = invoke(home, "verify-export", str(export))

        assert code != 0
        assert envelope["error"]["code"] == "forge_export_changed"


def test_an_export_readme_is_checked_against_its_recorded_fingerprint(
    home: Path,
    proposal_id: str,
    profiles: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The README is checked byte for byte against the sha256 export.json
    records for it, never written again, so a later Techtree that words its
    READMEs differently still checks an earlier export."""
    collection_id = accepted(home, proposal_id, profiles)
    export = tmp_path / "export"
    assert invoke(home, "export", collection_id, "--to", str(export))[0] == 0

    def never(*_: object, **__: object) -> str:
        raise AssertionError("checking an export does not write its README")

    monkeypatch.setattr("techtree.forge.export.export_readme", never)
    assert invoke(home, "verify-export", str(export))[0] == 0

    readme = export / "README.md"
    readme.write_bytes(readme.read_bytes() + b"\n")
    code, envelope = invoke(home, "verify-export", str(export))

    assert code != 0
    assert envelope["error"]["code"] == "forge_export_changed"


def test_an_export_is_imported_whole_or_not_at_all(
    home: Path,
    proposal_id: str,
    profiles: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A changed export is refused before anything is written, and one whose
    task does not qualify on the importing computer leaves nothing behind."""
    collection_id = accepted(home, proposal_id, profiles)
    export = tmp_path / "export"
    assert invoke(home, "export", collection_id, "--to", str(export))[0] == 0
    fresh = tmp_path / "fresh-home"
    fresh.mkdir()
    paths = paths_from_root(fresh)
    # Tests that pass when nothing is done do not qualify a task.
    docker = FakeDocker(reward=1.0)
    monkeypatch.setattr("techtree.cli.commands.forge.run_command", docker)
    instruction = min((export / "tasks").iterdir()) / "instruction.md"
    original = instruction.read_bytes()

    instruction.write_bytes(original + b" ")
    code, changed = invoke(fresh, "import", str(export))

    assert code != 0
    assert changed["error"]["code"] == "forge_export_changed"
    assert docker.calls == []
    assert not paths.forge_collections_dir.exists()

    instruction.write_bytes(original)
    code, unqualified = invoke(fresh, "import", str(export))

    assert code != 0
    assert unqualified["error"]["code"] == "forge_import_not_qualified"
    assert "Nothing was imported" in unqualified["error"]["message"]
    assert docker.graded()
    assert not paths.forge_collections_dir.exists()
    assert list(paths.forge_builds_dir.iterdir()) == []


def test_an_export_built_for_another_platform_is_not_imported(
    home: Path,
    proposal_id: str,
    profiles: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Techtree runs tasks only on the Docker platform they were built for."""
    collection_id = accepted(home, proposal_id, profiles)
    export = tmp_path / "export"
    assert invoke(home, "export", collection_id, "--to", str(export))[0] == 0
    fresh = tmp_path / "fresh-home"
    fresh.mkdir()
    docker = FakeDocker(reward=0.0, reference_reward=1.0)
    monkeypatch.setattr("techtree.cli.commands.forge.run_command", docker)
    built_for = host_docker_platform()
    other = "linux/arm64" if built_for == "linux/amd64" else "linux/amd64"
    monkeypatch.setattr("techtree.forge.export.host_docker_platform", lambda: other)

    code, envelope = invoke(fresh, "import", str(export))

    assert code != 0
    assert envelope["error"]["code"] == "forge_import_other_platform"
    assert envelope["error"]["details"] == {
        "platform": other,
        "built_for": [built_for],
    }
    assert docker.calls == []
    assert not paths_from_root(fresh).forge_builds_dir.exists()


def test_a_failed_import_removes_only_the_folders_it_made(
    home: Path,
    proposal_id: str,
    profiles: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Another import that makes the collection's folder while this one is
    qualifying its tasks keeps it; this one removes only its own builds."""
    collection_id = accepted(home, proposal_id, profiles)
    export = tmp_path / "export"
    assert invoke(home, "export", collection_id, "--to", str(export))[0] == 0
    fresh = tmp_path / "fresh-home"
    fresh.mkdir()
    paths = paths_from_root(fresh)
    theirs = paths.forge_collection_dir(collection_id)
    docker = FakeDocker(reward=0.0, reference_reward=1.0)

    def racing(argv: Sequence[str], timeout: float) -> Any:
        if not theirs.exists():
            theirs.mkdir(parents=True)
            (theirs / "collection.json").write_text("{}", encoding="utf-8")
        return docker(argv, timeout)

    monkeypatch.setattr("techtree.cli.commands.forge.run_command", racing)

    code, envelope = invoke(fresh, "import", str(export))

    assert code != 0
    assert envelope["error"]["code"] == "forge_import_exists"
    assert docker.graded()
    assert (theirs / "collection.json").read_text(encoding="utf-8") == "{}"
    assert list(paths.forge_builds_dir.iterdir()) == []


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
    do, and needs as many graded pairs as every other verdict; a line of the
    Skill the tasks were written from, or of a task the reviser could see,
    does not stop it being judged, but held-out material any Skill before it
    carried does, however many revisions it passed through."""
    shared = "Each line of amounts.txt holds one whole number, nothing else."
    original = SKILL.splitlines()[-1]

    def with_notes(name: str) -> FakePlanner:
        answer = json.loads(created_package(name))
        answer["files"].append(
            {
                "path": "environment/notes.txt",
                "text": shared + "\n",
                "executable": False,
            }
        )
        [rubric] = [
            file for file in answer["files"] if file["path"] == "tests/rubric.md"
        ]
        rubric["text"] += original + "\n"
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
            body=f"Add them, then write.\n\n{original}\n\n{shared}",
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

    parent = judged
    for generation, body in enumerate(
        (f"Sum.\n\n{SOLVE_LINE}", f"Sum, then check.\n\n{SOLVE_LINE}")
    ):
        revised = write_skill(
            tmp_path / f"laundered-{generation}", name="branch-code", body=body
        )
        revision = prepare_revision(
            paths, comparison_id=parent, skill_root=revised, label=None
        )
        assert held_out in {finding.task_id for finding in revision.record.screening}
        measured = measure_revision(
            paths,
            revision.revision_id,
            runner(RewardByTask({studied: 0.0, held_out: 1.0})),
        )
        assert measured.revision.record.verdict is not None
        assert "is not judged" in measured.revision.record.verdict
        parent = measured.comparison.comparison_id


def test_a_task_keeps_its_part_in_every_later_version(
    tmp_path: Path, home: Path, proposal_id: str, profiles: Path
) -> None:
    """Invariant: a task's part, once given, holds as tasks are added,
    removed, added again and built again, and in a collection of another
    Skill; a new first version of the same Skill's tasks, a version of an
    older one, and a second version of the same one are refused; a Skill
    derived from it stays in its line."""
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
    unrelated = tmp_path / "unrelated" / "branch-code"
    unrelated.mkdir(parents=True)
    (unrelated / "SKILL.md").write_text(
        SKILL + "2. Answer in capitals.\n", encoding="utf-8"
    )
    _, apart = invoke(home, "inspect-skill", str(unrelated))
    v7 = accepted_version(
        construct(
            home,
            propose(tmp_path, home, profiles, apart["facts"]["source_id"]),
            profiles,
            FakeCreator(),
        )
    )

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
    for version in (v1, v2, v3, v4, v5, v6, v7):
        for name, part in version.items():
            assert given.setdefault(name, part) == part, name
    for collection_id in versions:
        assert invoke(home, "verify", collection_id)[0] == 0, collection_id

    unreadable = paths.forge_collections_dir / ("forgecol_" + "0" * 32)
    unreadable.mkdir()
    (unreadable / "collection.json").write_text("{}", encoding="utf-8")
    for arguments in (("status", derived), ("collect", derived)):
        _, refused = invoke(home, *arguments)
        assert refused["error"]["code"] == "forge_collection_unreadable"
        assert str(unreadable) in refused["error"]["message"]
