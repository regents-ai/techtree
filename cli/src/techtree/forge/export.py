"""A private copy of one accepted collection, checking one from its files
alone, and bringing one into another Techtree home.

``docs/plan/v0.3.0-task-set.md`` T12 (R39-R41) and §6 P3. ``forge export`` verifies the
collection in this home first, then writes a new folder holding exactly:
each member's task files, copied entry by entry from its build's commitment;
``export.json``, the collection record and acceptance with each member's
build record and qualification evidence; and a README saying what the folder
holds and leaves out, and which tasks are held out. The Source Skill's
bytes, the authoring and qualification logs, and everything else in the home
are never read. The folder is written beside its destination under a hidden
name, checked, and only then renamed into place; it is the owner's alone, and
nothing is published.

``forge verify-export`` trusts nothing but the folder: every file is hashed
again against the accepted content digests, each qualification record against
its member digest, which tasks are held out against the rule that picks
them, the membership and collection digests against the acceptance, and the
README against ``export.json`` and the tasks' own time limits. Anything the
folder holds beyond the collection, or lacks, is a changed export. What the
folder can only state, not show, is listed as recorded only.

``forge import`` brings a verified export into a Techtree home so that
``forge run --collection`` and ``forge compare`` work on it as on a collection
accepted there. It checks the folder first and refuses anything
``verify-export`` refuses. Every task is admitted again and qualified on this
computer, under the build id it had, and the collection is written exactly as
it was accepted, with the same id, the same parts and the same digests, so a
comparison made here names the same collection as one made where it was
accepted. Beside it, a record says where it came from and keeps the exported
qualification records its digests name. Nothing is written until every task
has qualified here; a failure removes what the import wrote.
"""

from __future__ import annotations

import os
import shutil
import stat
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from pydantic import ValidationError as ModelValidationError

from techtree.doctor.checks import SUPPORTED_PYTHON
from techtree.errors import ConflictError, NotFoundError, RunError, ValidationError
from techtree.forge.collection import (
    accepted_evidence,
    check_importable,
    member_records_match,
    record_imported_collection,
    verify_collection,
)
from techtree.forge.content import changed_entries, commit_task_set
from techtree.forge.docker import Docker
from techtree.forge.models import (
    FORGE_COLLECTION_IMPORT_SCHEMA_VERSION,
    FORGE_EXPORT_SCHEMA_VERSION,
    TASK_KIND_WORDS,
    TASK_KINDS_EXPLAINED,
    ForgeCollectionImport,
    ForgeCollectionMember,
    ForgeCollectionStatus,
    ForgeExport,
    ForgeExportTask,
    ForgeExportVerification,
    TaskContentManifest,
    TaskQualification,
)
from techtree.forge.process import CommandRunner
from techtree.forge.profile import CREATE_PROFILE_COMMAND, PROFILE_NAME, sign_in_command
from techtree.forge.qualify import read_skill_task_facts
from techtree.forge.report import first_failed_check
from techtree.forge.run import AGENT_MARGIN_SECONDS
from techtree.forge.service import import_build, read_build_status
from techtree.forge.skill2env import local_source_skill
from techtree.fs import (
    atomic_write_json,
    atomic_write_text,
    open_exclusive,
    remove_tree,
)
from techtree.models.cli import invocation, invocation_line
from techtree.paths import TechtreePaths

__all__ = [
    "README_PLACEHOLDERS",
    "export_collection",
    "export_readme",
    "import_export",
    "verify_export",
]

EXPORT_FILENAME: Final = "export.json"
README_FILENAME: Final = "README.md"
TASKS_DIRNAME: Final = "tasks"

#: What checking an export works out again from its files.
CHECKED: Final = (
    "every file of every task, against the fingerprints the collection accepted",
    "each task's qualification record, against the collection",
    "the collection's members and fingerprint, against the acceptance",
    "which tasks are held out, against the rule that picks them from the "
    "tasks and the parts earlier versions gave them",
    "the README, against export.json and the tasks' own time limits",
)

#: What an export states and its files cannot show.
RECORDED_ONLY: Final = (
    "the Skill the tasks were written from: its name and fingerprint are "
    "recorded, its text is not included",
    "the proposal and the building of the tasks",
    "the qualification runs: their results are recorded, not run again",
    "the images the tasks were built and checked with",
    "the acceptance itself: when it was given and how it was answered",
    "the parts earlier versions of the collection gave their tasks",
)


def export_collection(
    paths: TechtreePaths, collection_id: str, destination: Path
) -> ForgeExportVerification:
    """Write a checked private copy of an accepted collection to a new folder."""
    status = verify_collection(paths, collection_id)
    assert status.acceptance is not None  # a verified collection was accepted
    destination = destination.expanduser().absolute()
    if destination.exists() or destination.is_symlink():
        raise ConflictError(
            f"{destination} already exists; an export is written to a new folder",
            code="forge_export_exists",
            details={"path": str(destination)},
        )
    if not destination.parent.is_dir():
        raise NotFoundError(
            f"there is no folder {destination.parent} to write the export in",
            code="forge_export_no_folder",
            details={"path": str(destination.parent)},
        )
    staging = Path(
        tempfile.mkdtemp(
            dir=destination.parent, prefix=f".{destination.name}.", suffix=".partial"
        )
    )
    try:
        (staging / TASKS_DIRNAME).mkdir(mode=0o700)
        tasks = [
            _export_task(paths, member, evidence, staging / TASKS_DIRNAME)
            for member, evidence in zip(
                status.record.review.members,
                accepted_evidence(paths, status),
                strict=True,
            )
        ]
        export = ForgeExport(
            schema_version=FORGE_EXPORT_SCHEMA_VERSION,
            exported_at=datetime.now(UTC),
            collection=status.record,
            acceptance=status.acceptance,
            tasks=tasks,
        )
        atomic_write_json(staging / EXPORT_FILENAME, export.model_dump(mode="json"))
        atomic_write_text(
            staging / README_FILENAME, export_readme(export, staging / TASKS_DIRNAME)
        )
        verification = verify_export(staging)
        staging.rename(destination)
    except BaseException:
        remove_tree(staging)
        raise
    return verification.model_copy(update={"path": str(destination)})


def _export_task(
    paths: TechtreePaths,
    member: ForgeCollectionMember,
    evidence: TaskQualification,
    tasks_dir: Path,
) -> ForgeExportTask:
    status = read_build_status(paths, member.build_id)
    build = status.build
    assert build is not None  # a verified member
    [manifest] = build.task_set.tasks
    _copy(
        Path(status.tasks_path) / member.task_id, tasks_dir / member.task_id, manifest
    )
    return ForgeExportTask(build=build, qualification=evidence)


def _copy(source: Path, target: Path, manifest: TaskContentManifest) -> None:
    """Copy exactly the committed entries, never following a link."""
    target.mkdir(mode=0o700)
    for entry in manifest.entries:
        if entry.kind == "directory":
            (target / entry.path).mkdir(mode=0o700)
            continue
        descriptor = os.open(
            source / entry.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
        )
        with (
            os.fdopen(descriptor, "rb") as reader,
            open_exclusive(
                target / entry.path, 0o700 if entry.executable else 0o600
            ) as writer,
        ):
            shutil.copyfileobj(reader, writer)


# ---------------------------------------------------------------------------
# Checking an export
# ---------------------------------------------------------------------------


def verify_export(root: Path) -> ForgeExportVerification:
    """Check an export from its folder alone and say what that could show."""
    return _verified(root)[1]


def _verified(root: Path) -> tuple[ForgeExport, ForgeExportVerification]:
    root = root.expanduser().absolute()
    export = _read(root)
    review = export.collection.review
    _require_listing(
        root,
        dict.fromkeys((member.task_id for member in review.members), True),
        within=f"{TASKS_DIRNAME}/",
    )
    if (
        export.acceptance.collection_id != export.collection.collection_id
        or export.acceptance.collection_digest != export.collection.collection_digest
    ):
        raise _changed(root, "the acceptance does not name this collection")
    if len(export.tasks) != len(review.members):
        raise _changed(root, "its task records do not match the collection's tasks")
    for member, task in zip(review.members, export.tasks, strict=True):
        _require_records(root, member, task)
    try:
        observed = commit_task_set(
            root / TASKS_DIRNAME, [member.task_id for member in review.members]
        )
    except RunError as error:
        raise _changed(root, error.message) from error
    for member, task, found in zip(
        review.members, export.tasks, observed.tasks, strict=True
    ):
        if found.content_digest != member.content_digest:
            [accepted] = task.build.task_set.tasks
            raise _changed(
                root,
                f"in task {member.task_name}, these differ from what was "
                "accepted: " + ", ".join(changed_entries(accepted, found)),
            )
    readme = export_readme(export, root / TASKS_DIRNAME)
    if (root / README_FILENAME).read_bytes() != readme.encode():
        raise _changed(root, "the README differs from what export.json says")
    return export, ForgeExportVerification(
        path=str(root),
        collection_id=export.collection.collection_id,
        version=review.version,
        tasks=len(review.members),
        held_out=sum(member.part == "held_out" for member in review.members),
        checked=list(CHECKED),
        recorded_only=list(RECORDED_ONLY),
    )


def _read(root: Path) -> ForgeExport:
    if not (root / EXPORT_FILENAME).is_file():
        raise NotFoundError(
            f"{root} is not a Techtree export: it has no {EXPORT_FILENAME}",
            code="forge_export_not_found",
            details={"path": str(root)},
        )
    _require_listing(
        root, {EXPORT_FILENAME: False, README_FILENAME: False, TASKS_DIRNAME: True}
    )
    try:
        return ForgeExport.model_validate_json((root / EXPORT_FILENAME).read_bytes())
    except ModelValidationError as error:
        issue = error.errors(include_input=False, include_url=False)[0]
        raise _changed(
            root, f"{EXPORT_FILENAME} is not valid: {issue['msg']}"
        ) from error


def _require_listing(root: Path, expected: dict[str, bool], within: str = "") -> None:
    """Refuse anything a folder holds beyond ``expected``, or lacks, or links.

    ``expected`` maps each name to whether it is a folder; anything else is a
    plain file, and a link is neither.
    """
    directory = root / within
    found = {name: os.lstat(directory / name).st_mode for name in os.listdir(directory)}
    extra = sorted(within + name for name in found if name not in expected)
    if extra:
        raise _changed(
            root, f"it holds {', '.join(extra)}, which the collection does not"
        )
    missing = sorted(within + name for name in expected if name not in found)
    if missing:
        raise _changed(root, f"{', '.join(missing)} is missing")
    wrong = sorted(
        within + name
        for name, folder in expected.items()
        if not (stat.S_ISDIR if folder else stat.S_ISREG)(found[name])
    )
    if wrong:
        raise _changed(
            root, f"{', '.join(wrong)} is not a plain file or folder as written"
        )


def _require_records(
    root: Path, member: ForgeCollectionMember, task: ForgeExportTask
) -> None:
    """A member's build and qualification records are the ones it accepted."""
    if not member_records_match(member, task.build, task.qualification):
        raise _changed(
            root, f"the records of task {member.task_name} are not the ones accepted"
        )


def _changed(root: Path, what: str) -> ValidationError:
    return ValidationError(
        f"the export at {root} is not the collection it copies: {what}",
        code="forge_export_changed",
        details={"path": str(root), "what": what},
    )


# ---------------------------------------------------------------------------
# Bringing an export into a home
# ---------------------------------------------------------------------------


def import_export(
    paths: TechtreePaths, root: Path, run: CommandRunner
) -> ForgeCollectionStatus:
    """Bring a verified export into this home as the collection it copies.

    Refuses anything ``verify-export`` refuses, a collection or build this
    home already holds, and a collection of a Skill whose collections this
    home already holds. Each task is admitted again from the folder and
    qualified here under its own build id; one that does not qualify stops
    the import, and everything it wrote is removed.
    """
    export, verification = _verified(root)
    root = Path(verification.path)
    record = export.collection
    check_importable(paths, record)
    for task in export.tasks:
        if paths.forge_build_dir(task.build.build_id).exists():
            raise ConflictError(
                f"build {task.build.build_id} is already in this Techtree home",
                code="forge_import_exists",
                details={"build_id": task.build.build_id},
            )
    docker = Docker(run)
    docker.require_daemon()
    written: list[Path] = []
    try:
        for member, task in zip(record.review.members, export.tasks, strict=True):
            written.append(paths.forge_build_dir(task.build.build_id))
            qualification = import_build(
                paths,
                docker,
                task.build,
                root / TASKS_DIRNAME / member.task_id,
                source_skill=local_source_skill(record.review.source_name),
            ).qualification
            assert qualification is not None  # import_build qualified it
            [here] = qualification.tasks
            if not here.qualified:
                failed = first_failed_check(here)
                raise RunError(
                    f"task {member.task_name} did not qualify on this computer"
                    + ("" if failed is None else f": {failed.detail}")
                    + ". Nothing was imported",
                    code="forge_import_not_qualified",
                    details={"task_id": member.task_id, "build_id": member.build_id},
                )
        written.append(paths.forge_collection_dir(record.collection_id))
        return record_imported_collection(
            paths,
            record,
            export.acceptance,
            ForgeCollectionImport(
                schema_version=FORGE_COLLECTION_IMPORT_SCHEMA_VERSION,
                collection_id=record.collection_id,
                imported_at=datetime.now(UTC),
                exported_at=export.exported_at,
                origin=str(root),
                qualifications=[task.qualification for task in export.tasks],
            ),
        )
    except BaseException:
        for directory in written:
            remove_tree(directory)
        raise


# ---------------------------------------------------------------------------
# The README
# ---------------------------------------------------------------------------

#: The words the README's commands hold in place of what only its reader
#: knows, and what each stands for.
README_PLACEHOLDERS: Final = {
    "EXPORT_FOLDER": "this folder",
    "SKILL_FOLDER": "the folder holding the Skill and its SKILL.md",
    "PROVIDER": "the provider Hermes will be asked for, by the name Hermes uses",
    "MODEL": "the model Hermes will be asked for",
    "BASELINE_RUN_ID": "the id the run without the Skill prints",
    "CANDIDATE_RUN_ID": "the id the run with the Skill prints",
}


def _reproduction(collection_id: str) -> list[str]:
    """The commands that check, import, run and compare an export, in order."""
    run = {"--collection": collection_id, "--provider": "PROVIDER", "--model": "MODEL"}
    return [
        " ".join(invocation_line(prepared))
        for prepared in (
            invocation("forge", "verify-export", arguments=["EXPORT_FOLDER"]),
            invocation("forge", "import", arguments=["EXPORT_FOLDER"]),
            invocation("forge", "inspect-skill", arguments=["SKILL_FOLDER"]),
            invocation("forge", "run", options={"--arm": "baseline", **run}),
            invocation(
                "forge",
                "run",
                options={"--arm": "candidate", **run, "--skill": "SKILL_FOLDER"},
            ),
            invocation(
                "forge", "compare", arguments=["BASELINE_RUN_ID", "CANDIDATE_RUN_ID"]
            ),
        )
    ]


def _python_versions() -> str:
    """The Python versions this Techtree runs on, in words."""
    (major, lowest), (ceiling_major, ceiling) = SUPPORTED_PYTHON
    assert major == ceiling_major  # one major version is supported
    return " or ".join(f"{major}.{minor}" for minor in range(lowest, ceiling))


def _duration(seconds: float) -> str:
    minutes = seconds / 60
    return f"{minutes:g} {'minute' if minutes == 1 else 'minutes'}"


def export_readme(export: ForgeExport, tasks_dir: Path) -> str:
    """The README an export carries, made from its ``export.json`` and its
    tasks' ``task.toml`` time limits, read from ``tasks_dir``."""
    record = export.collection
    review = record.review
    accepted = export.acceptance.accepted_at
    members = review.members
    lines = [
        f"# Collection {record.collection_id}, version {review.version}",
        "",
        "This folder is a private copy of one accepted collection of tasks, "
        f"made by Techtree on {export.exported_at:%Y-%m-%d at %H:%M} UTC. "
        "Nothing in it has been published.",
        "",
        "## What it holds",
        "",
        *(
            f"- `{TASKS_DIRNAME}/{member.task_id}/`: the task {member.task_name}"
            + (" (held out)" if member.part == "held_out" else "")
            + f", a {TASK_KIND_WORDS[member.kind]} for claim {member.claim}, with its "
            "instruction, the files it starts from, its tests and its reference "
            "solutions."
            for member in members
        ),
        f"- `{EXPORT_FILENAME}`: the collection as it was accepted on "
        f"{accepted:%Y-%m-%d at %H:%M} UTC, each task's qualification record, "
        "and where each task came from.",
        "",
        "The tasks marked held out are kept from any agent that improves a "
        "Skill on this collection, and a revised Skill's verdict is worked out "
        "on them alone. Which tasks are held out follows from a fixed rule; "
        "nobody chose it. A task keeps its part in every collection accepted "
        "after this one in the same Techtree home, whichever Skill it is for, "
        "even when it is built again or appears under another name with the "
        "same files; one "
        "that was ever studied is never held out. Tasks whose files differ only "
        "slightly are not recognised as the same task.",
        "",
        "## What the tasks test",
        "",
        *(
            line
            for claim in review.claims
            if claim.claim_id in {member.claim for member in members}
            for line in (
                f"- {claim.claim_id}: {claim.statement}",
                f"  - What shows it: {claim.observable}",
            )
        ),
        "",
        TASK_KINDS_EXPLAINED,
        "",
        "## What it leaves out",
        "",
        f"- The Skill the tasks were written from, {review.source_name}. Its name "
        "and fingerprint are recorded; its text is not included.",
        "- The conversations and logs from writing the tasks and from checking them.",
        "- Everything else on the computer it came from, such as settings, "
        "sign-ins and past runs.",
        "",
        "## Before you share it",
        "",
        "Each task's tests and reference solutions are included, so anyone who "
        "has this folder can read the answers. Give it only to people who check "
        "or run the tasks, never to an agent being tested on them.",
        "",
        "## Checking it",
        "",
        "`techtree forge verify-export` works out again, from the files here:",
        "",
        *(f"- {line}" for line in CHECKED),
        "",
        "It can only report what is recorded about:",
        "",
        *(f"- {line}" for line in RECORDED_ONLY),
        "",
        "## Running the tasks yourself",
        "",
        "With this folder and the Skill the tasks were written from, you can "
        "check the folder, run the tasks on your own computer without the Skill "
        "and with it, and compare the two. You need:",
        "",
        "- Docker, running. Every task is built and run in a container on your "
        "computer, with the network off.",
        "- Techtree, installed the way https://techtree.sh/start says. It is "
        "installed with uv, which also installs the Python it runs on, Python "
        f"{_python_versions()}.",
        "- Hermes Agent, as `hermes` on your PATH, with a profile named "
        f"{PROFILE_NAME} signed in to the provider you will use.",
        f"- The Skill the tasks were written from, {review.source_name}, in a "
        f"folder of its own. Its fingerprint is {review.source_digest}. `techtree "
        "forge inspect-skill` prints the start of it on its Kept line, so you "
        "can check you have the same Skill.",
        "",
        "Make the Hermes profile once:",
        "",
        "```",
        CREATE_PROFILE_COMMAND,
        sign_in_command("PROVIDER"),
        "```",
        "",
        "### What the model calls can cost",
        "",
        "Only time limits them. Each try gives the agent its task's own time "
        "limit, below, and Techtree stops it "
        f"{_duration(AGENT_MARGIN_SECONDS)} after that if it has not stopped. "
        "Nothing limits its turns or its tokens, so what a try costs depends on "
        "the model and the provider you choose. Running every task once is "
        f"{len(members)} tries without the Skill and {len(members)} with it; "
        "`--repetitions N` on `techtree forge run` runs each task N times.",
        "",
        *(
            f"- {member.task_name}: "
            + _duration(read_skill_task_facts(tasks_dir / member.task_id).agent_timeout)
            for member in members
        ),
        "",
        "### The commands, in order",
        "",
        "```",
        *_reproduction(record.collection_id),
        "```",
        "",
        "; ".join(
            f"{placeholder} is {meaning}"
            for placeholder, meaning in README_PLACEHOLDERS.items()
        )
        + ".",
        "",
        "`techtree forge import` checks this folder as `verify-export` does, then "
        "admits each task again and checks it on your computer the way it was "
        "checked when it was built: its image is built with the network off, a "
        "run that does nothing must fail its tests, and its solutions must pass "
        "or fail them as they should. It calls no model. The collection keeps "
        "its id, its parts and its fingerprint, so the comparison names the same "
        "collection and the same tasks as one made where it was accepted. Each "
        "run shows what it will do and asks before it starts.",
        "",
        "Running every task, the held-out ones too, is right for checking a "
        "result: they are kept from an agent that improves the Skill, not from "
        "you.",
        "",
    ]
    return "\n".join(lines)
