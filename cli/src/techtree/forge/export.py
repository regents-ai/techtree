"""A private copy of one accepted collection, and checking one from its files alone.

``docs/plan/v0.3.0-task-set.md`` T12 (R39-R41). ``forge export`` verifies the
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
README against ``export.json``. Anything the folder holds beyond the
collection, or lacks, is a changed export. What the folder can only state,
not show, is listed as recorded only.
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

from techtree.canonical import digest_object
from techtree.errors import ConflictError, NotFoundError, RunError, ValidationError
from techtree.forge.collection import verify_collection
from techtree.forge.content import changed_entries, commit_task_set, task_fingerprint
from techtree.forge.models import (
    FORGE_EXPORT_SCHEMA_VERSION,
    TASK_KIND_WORDS,
    TASK_KINDS_EXPLAINED,
    ForgeCollectionMember,
    ForgeExport,
    ForgeExportTask,
    ForgeExportVerification,
    TaskContentManifest,
)
from techtree.forge.service import read_build_status
from techtree.fs import (
    atomic_write_json,
    atomic_write_text,
    open_exclusive,
    remove_tree,
)
from techtree.paths import TechtreePaths

__all__ = ["export_collection", "export_readme", "verify_export"]

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
    "the README, against export.json",
)

#: What an export states and its files cannot show.
RECORDED_ONLY: Final = (
    "the Skill the tasks were written from: its fingerprint is recorded, its "
    "text is not included",
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
            _export_task(paths, member, staging / TASKS_DIRNAME)
            for member in status.record.review.members
        ]
        export = ForgeExport(
            schema_version=FORGE_EXPORT_SCHEMA_VERSION,
            exported_at=datetime.now(UTC),
            collection=status.record,
            acceptance=status.acceptance,
            tasks=tasks,
        )
        atomic_write_json(staging / EXPORT_FILENAME, export.model_dump(mode="json"))
        atomic_write_text(staging / README_FILENAME, export_readme(export))
        verification = verify_export(staging)
        staging.rename(destination)
    except BaseException:
        remove_tree(staging)
        raise
    return verification.model_copy(update={"path": str(destination)})


def _export_task(
    paths: TechtreePaths, member: ForgeCollectionMember, tasks_dir: Path
) -> ForgeExportTask:
    status = read_build_status(paths, member.build_id)
    build, qualification = status.build, status.qualification
    assert build is not None and qualification is not None  # a verified member
    [manifest] = build.task_set.tasks
    _copy(
        Path(status.tasks_path) / member.task_id, tasks_dir / member.task_id, manifest
    )
    return ForgeExportTask(
        build=build,
        qualification=next(
            task for task in qualification.tasks if task.task_id == member.task_id
        ),
    )


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
    if (root / README_FILENAME).read_bytes() != export_readme(export).encode():
        raise _changed(root, "the README differs from what export.json says")
    return ForgeExportVerification(
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
    manifests = task.build.task_set.tasks
    evidence = task.qualification
    if (
        task.build.build_id != member.build_id
        or [manifest.task_id for manifest in manifests] != [member.task_id]
        or manifests[0].content_digest != member.content_digest
        or task_fingerprint(manifests[0]) != member.fingerprint
        or evidence.task_id != member.task_id
        or evidence.task_content_digest != member.content_digest
        or not evidence.qualified
        or digest_object(evidence) != member.qualification_digest
    ):
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
# The README
# ---------------------------------------------------------------------------


def export_readme(export: ForgeExport) -> str:
    """The README an export carries, made from its ``export.json`` alone."""
    record = export.collection
    review = record.review
    accepted = export.acceptance.accepted_at
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
            for member in review.members
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
            if claim.claim_id in {member.claim for member in review.members}
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
        "- The Skill the tasks were written from. Its fingerprint is recorded; "
        "its text is not included.",
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
        "```",
        "techtree forge verify-export <this folder>",
        "```",
        "",
        "This works out again, from the files here:",
        "",
        *(f"- {line}" for line in CHECKED),
        "",
        "It can only report what is recorded about:",
        "",
        *(f"- {line}" for line in RECORDED_ONLY),
        "",
        "## Running the tasks",
        "",
        "Running the tasks from this folder is not offered yet. On the computer "
        "that made it, a run without the Skill starts with:",
        "",
        "```",
        f"techtree forge run --arm baseline --collection {record.collection_id} "
        "--provider PROVIDER --model MODEL",
        "```",
        "",
    ]
    return "\n".join(lines)
