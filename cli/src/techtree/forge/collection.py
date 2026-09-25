"""Accepting qualified tasks as one frozen collection, and checking it again.

``docs/plan/v0.3.0-skill-environments.md`` (U4, R29, R33-R34, AE5).

Qualification says which built tasks work; it accepts nothing. A collection
is prepared from a construction and the constructions it retried: its review
lists every task of the proposal with how it went last time it was tried,
failures included, and the exact members, the qualified tasks being accepted
(all of them unless a person names fewer), each by the digest of its files
and of its qualification. Preparing refuses when nothing qualified.

Accepting records a person's decision on exactly that review, by its digest,
and freezes the collection: an accepted collection is never accepted again or
changed. A different membership, or a task built again, is a new collection
naming the one it replaces, one version later; one with the same members as
the version it replaces is refused.

Every member is in one of two parts, given by a fixed rule rather than
chosen by anyone (founder decision 2a, ``docs/plan/v0.3.0-task-set.md`` §6):
the tasks an improving agent may study, and the tasks held out from it, on
which a revised Skill's verdict is computed. A task takes the part of every
task an earlier version of the collection held under its name or with its
files, and is studied when those disagree, so a task built again keeps its
part and a task once studied is never held out; only a task that shares
neither with an earlier one is given a part by its fingerprint. Earlier
versions are the chain ``--previous`` names, so a Skill whose tasks were
already accepted in a collection is collected again only as a new version of
it: a first version is refused when the home holds an accepted collection of
the same Skill. A collection holds at least one task in each part and no two
tasks with the same files, and preparing refuses one that would not; tasks
whose files differ only slightly are not recognised as the same.

Verifying an accepted collection makes its review again from what is on disk
now: every member's files are hashed against their build's commitment, every
qualification is read back, and the digest must be the one accepted. Anything
else is refused as a changed collection.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Final, NamedTuple

from pydantic import ValidationError as ModelValidationError

from techtree.canonical import digest_object
from techtree.errors import ConflictError, NotFoundError, TechtreeError, ValidationError
from techtree.forge.authoring import AnsweredWith, ReviewedOn
from techtree.forge.construction import read_construction_status
from techtree.forge.content import (
    changed_entries,
    commit_task_set,
    task_fingerprint,
    verify_task_set,
)
from techtree.forge.models import (
    FORGE_COLLECTION_ACCEPTANCE_SCHEMA_VERSION,
    FORGE_COLLECTION_SCHEMA_VERSION,
    MINIMUM_COLLECTION_TASKS,
    ForgeCollectionAcceptance,
    ForgeCollectionCandidate,
    ForgeCollectionMember,
    ForgeCollectionParent,
    ForgeCollectionRecord,
    ForgeCollectionReview,
    ForgeCollectionState,
    ForgeCollectionStatus,
    ForgeConstructionStatus,
    ForgeConstructionTaskStatus,
    ForgeTaskKind,
    collection_parts,
)
from techtree.forge.planning import read_proposal_status
from techtree.forge.service import read_build_status
from techtree.fs import atomic_write_json
from techtree.ids import new_id, validate_id
from techtree.paths import TechtreePaths

__all__ = [
    "accept_collection",
    "changed_member_files",
    "check_collection",
    "latest_collection",
    "prepare_collection",
    "qualified_tasks",
    "read_collection_status",
    "verify_collection",
]

COLLECTION_FILENAME: Final = "collection.json"
ACCEPTANCE_FILENAME: Final = "acceptance.json"


def prepare_collection(
    paths: TechtreePaths,
    *,
    construction_id: str,
    task_names: list[str] | None,
    previous: str | None,
) -> ForgeCollectionStatus:
    """Write the review of one collection, accepting nothing."""
    if previous is None:
        _require_first(paths, construction_id)
    review = _review(
        paths,
        construction_id=construction_id,
        task_names=task_names,
        previous=previous,
    )
    collection_id = new_id("forgecol")
    directory = paths.forge_collection_dir(collection_id)
    directory.mkdir(parents=True, mode=0o700)
    record = ForgeCollectionRecord(
        schema_version=FORGE_COLLECTION_SCHEMA_VERSION,
        collection_id=collection_id,
        created_at=datetime.now(UTC),
        review=review,
        collection_digest=digest_object(review),
    )
    atomic_write_json(directory / COLLECTION_FILENAME, record.model_dump(mode="json"))
    return read_collection_status(paths, collection_id)


def latest_collection(
    paths: TechtreePaths, construction_id: str
) -> ForgeCollectionStatus | None:
    """Return the latest accepted collection of the same Skill as a
    construction's tasks, if the home holds one.

    Collections are of the same Skill when their Source Skills have the same
    admitted files: the tasks are written from those bytes, whichever time
    the Skill was looked at or planned for. The latest is the highest
    version, the last accepted among equals.
    """
    source_digest = _chain(paths, construction_id)[0].record.review.source_digest
    directory = paths.forge_collections_dir
    accepted = [
        (status, status.acceptance.accepted_at)
        for status in (
            read_collection_status(paths, child.name)
            for child in (sorted(directory.iterdir()) if directory.is_dir() else [])
            if (child / COLLECTION_FILENAME).is_file()
        )
        if status.acceptance is not None
        and status.record.review.source_digest == source_digest
    ]
    if not accepted:
        return None
    latest, _ = max(
        accepted, key=lambda found: (found[0].record.review.version, found[1])
    )
    return latest


def _require_first(paths: TechtreePaths, construction_id: str) -> None:
    """Refuse a first version when a collection of the same Skill was
    accepted, since a new line of versions could give a task seen in one the
    other part in the other."""
    latest = latest_collection(paths, construction_id)
    if latest is None:
        return
    raise ValidationError(
        f"collection {latest.collection_id} (version "
        f"{latest.record.review.version}) already holds accepted tasks of this "
        "Skill, and a task keeps its part only within one line of versions. "
        "Make this a new version of it with forge collect "
        f"{construction_id} --previous {latest.collection_id}",
        code="forge_collection_has_versions",
        details={"construction_id": construction_id, "latest": latest.collection_id},
    )


def check_collection(paths: TechtreePaths, collection_id: str) -> ForgeCollectionStatus:
    """Refuse a collection already accepted, or whose review has changed."""
    status = read_collection_status(paths, collection_id)
    if status.acceptance is not None:
        raise ConflictError(
            f"collection {collection_id} was accepted and is frozen. A change "
            "is a new version: prepare it with forge collect --previous "
            f"{collection_id}",
            code="forge_collection_accepted",
            details={"collection_id": collection_id},
        )
    _require_same(paths, status, code="forge_collection_stale")
    return status


def accept_collection(
    paths: TechtreePaths,
    collection_id: str,
    *,
    reviewed_on: ReviewedOn,
    answered_with: AnsweredWith,
) -> ForgeCollectionStatus:
    """Record a person's acceptance of exactly the reviewed collection."""
    status = check_collection(paths, collection_id)
    acceptance = ForgeCollectionAcceptance(
        schema_version=FORGE_COLLECTION_ACCEPTANCE_SCHEMA_VERSION,
        collection_id=collection_id,
        collection_digest=status.record.collection_digest,
        accepted_at=datetime.now(UTC),
        reviewed_on=reviewed_on,
        answered_with=answered_with,
    )
    atomic_write_json(
        Path(status.path) / ACCEPTANCE_FILENAME, acceptance.model_dump(mode="json")
    )
    return read_collection_status(paths, collection_id)


def verify_collection(
    paths: TechtreePaths, collection_id: str
) -> ForgeCollectionStatus:
    """Check an accepted collection against its files and records, byte for byte."""
    status = read_collection_status(paths, collection_id)
    if status.acceptance is None:
        raise ValidationError(
            f"collection {collection_id} has not been accepted, so there is no "
            "frozen collection to verify yet",
            code="forge_collection_not_accepted",
            details={"collection_id": collection_id},
        )
    if status.acceptance.collection_digest != status.record.collection_digest:
        raise ValidationError(
            f"collection {collection_id} was changed after its acceptance: "
            "its review no longer has the digest a person accepted",
            code="forge_collection_changed",
            details={
                "collection_id": collection_id,
                "accepted": status.acceptance.collection_digest,
                "found": status.record.collection_digest,
            },
        )
    _require_same(paths, status, code="forge_collection_changed")
    return status


def _require_same(
    paths: TechtreePaths, status: ForgeCollectionStatus, *, code: str
) -> None:
    """Make the review again from disk and refuse it when it differs."""
    stored = status.record.review
    try:
        current = _review(
            paths,
            construction_id=stored.constructions[0],
            task_names=[member.task_name for member in stored.members],
            previous=None if stored.previous is None else stored.previous.collection_id,
        )
    except TechtreeError as error:
        raise ValidationError(
            f"collection {status.collection_id} no longer matches its records: "
            f"{error.message}",
            code=code,
            details={"collection_id": status.collection_id, "cause": error.code},
        ) from error
    found = digest_object(current)
    if found != status.record.collection_digest:
        changed = [
            name
            for name in _CHANGED_WORDS
            if getattr(current, name) != getattr(stored, name)
        ]
        raise ValidationError(
            f"collection {status.collection_id} no longer matches its records: "
            + ", ".join(dict.fromkeys(_CHANGED_WORDS[name] for name in changed))
            + " changed",
            code=code,
            details={
                "collection_id": status.collection_id,
                "reviewed": status.record.collection_digest,
                "found": found,
                "changed": list(changed),
            },
        )


#: Every part of a review that can differ when it is made again, in words.
_CHANGED_WORDS: Final = {
    "proposal_id": "the proposal",
    "proposal_digest": "the proposal",
    "claims": "the proposal",
    "source_id": "the Skill",
    "source_digest": "the Skill",
    "constructions": "the constructions",
    "previous": "the version it replaces",
    "version": "the version number",
    "tasks": "the tasks' outcomes",
    "members": "the accepted tasks' files or qualification",
}


# ---------------------------------------------------------------------------
# The review
# ---------------------------------------------------------------------------


def _review(
    paths: TechtreePaths,
    *,
    construction_id: str,
    task_names: list[str] | None,
    previous: str | None,
) -> ForgeCollectionReview:
    chain = _chain(paths, construction_id)
    newest = chain[0].record.review
    proposal = read_proposal_status(paths, newest.proposal_id).record
    candidates = [
        _candidate(name, chain) for name in (task.name for task in proposal.tasks)
    ]
    by_name = {candidate.task_name: candidate for candidate in candidates}
    names = (
        [candidate.task_name for candidate in candidates if candidate.usable]
        if task_names is None
        else task_names
    )
    if not names:
        raise ValidationError(
            f"no task of proposal {proposal.proposal_id} qualified, so there is "
            "nothing to accept. Every task's outcome is shown by forge status "
            f"{construction_id}",
            code="forge_collection_empty",
            details={"construction_id": construction_id},
        )
    for name in names:
        if name not in by_name or not by_name[name].usable:
            raise ValidationError(
                f"{name} is not a qualified task of proposal "
                f"{proposal.proposal_id}; only qualified tasks can be accepted",
                code="forge_collection_task_not_usable",
                details={"task_name": name, "proposal_id": proposal.proposal_id},
            )
    if len(names) < MINIMUM_COLLECTION_TASKS:
        left_out = [
            candidate.task_name
            for candidate in candidates
            if candidate.usable and candidate.task_name not in names
        ]
        raise ValidationError(
            f"this collection would hold only {', '.join(names)}, and a collection "
            f"needs at least {MINIMUM_COLLECTION_TASKS} tasks: some the improving "
            "agent may study, and some held out from it that decide whether a "
            "revised Skill improved. "
            + (
                f"{', '.join(left_out)} also qualified but "
                f"{'was' if len(left_out) == 1 else 'were'} left out by --task; "
                "name more tasks, or leave out --task to collect every one that "
                "qualified"
                if left_out
                else "Propose more tasks, or build the ones that did not qualify "
                f"again with forge construct --retry-of {construction_id}, then "
                "collect again"
            ),
            code="forge_collection_too_few",
            details={
                "construction_id": construction_id,
                "tasks": list(names),
                "left_out": list(left_out),
                "minimum": MINIMUM_COLLECTION_TASKS,
            },
        )
    parent = (
        None if previous is None else _parent(paths, previous, newest.source_digest)
    )
    committed = [_commit(paths, _last_try(name, chain)[1]) for name in names]
    for index, task in enumerate(committed):
        if same := next(
            (
                other
                for other in committed[:index]
                if other.fingerprint == task.fingerprint
            ),
            None,
        ):
            raise ValidationError(
                f"{same.task_name} and {task.task_name} have exactly the same "
                "files, so they are one task twice; a collection holds each task "
                "once. Leave one out with --task",
                code="forge_collection_duplicate_task",
                details={
                    "tasks": [same.task_name, task.task_name],
                    "fingerprint": task.fingerprint,
                },
            )
    parts = collection_parts(
        proposal.proposal_digest,
        [(task.task_name, task.fingerprint) for task in committed],
        [] if parent is None else parent.parts,
    )
    for missing in ("study", "held_out"):
        if missing not in parts:
            raise ValidationError(
                "every task of this collection would be "
                + (
                    "held out"
                    if missing == "study"
                    else "one the improving agent may study"
                )
                + ", because each takes the part an earlier version gave a task "
                "with its name or its files, and a collection needs at least one "
                "task in each part. Add a task no earlier version held, which is "
                "given the missing part, or keep a task an earlier version "
                + (
                    "let the improving agent study"
                    if missing == "study"
                    else "held out"
                ),
                code="forge_collection_too_few",
                details={
                    "construction_id": construction_id,
                    "tasks": list(names),
                    "missing": missing,
                },
            )
    members = [
        ForgeCollectionMember(**task._asdict(), part=part)
        for task, part in zip(committed, parts, strict=True)
    ]
    if parent is not None and members == (
        read_collection_status(paths, parent.collection_id).record.review.members
    ):
        raise ValidationError(
            f"these are exactly the tasks collection {parent.collection_id} "
            "accepted, so there is no new version to make",
            code="forge_collection_unchanged",
            details={"previous": parent.collection_id},
        )
    return ForgeCollectionReview(
        proposal_id=proposal.proposal_id,
        proposal_digest=proposal.proposal_digest,
        claims=proposal.claims,
        source_id=newest.source_id,
        source_digest=newest.source_digest,
        constructions=[status.construction_id for status in chain],
        previous=parent,
        version=1 if parent is None else parent.version + 1,
        tasks=candidates,
        members=members,
        membership_digest=digest_object(members),
    )


def changed_member_files(
    paths: TechtreePaths, member: ForgeCollectionMember
) -> list[str]:
    """Return the files of an accepted task that differ now from the ones its
    build committed to; raise when they cannot be read at all."""
    status = read_build_status(paths, member.build_id)
    assert status.build is not None  # a member's build qualified it
    [built] = status.build.task_set.tasks
    [found] = commit_task_set(Path(status.tasks_path), [member.task_id]).tasks
    return changed_entries(built, found)


def qualified_tasks(paths: TechtreePaths, construction_id: str) -> list[str]:
    """Return the tasks a collection of this ended construction could hold:
    those of its proposal whose last try, here or in a construction it
    retried, qualified."""
    chain = _chain(paths, construction_id)
    proposal = read_proposal_status(paths, chain[0].record.review.proposal_id).record
    return [task.name for task in proposal.tasks if _candidate(task.name, chain).usable]


def _chain(paths: TechtreePaths, construction_id: str) -> list[ForgeConstructionStatus]:
    """Return a construction and every one it retried, newest first."""
    chain = [read_construction_status(paths, construction_id)]
    if chain[0].state in {"prepared", "running"}:
        raise ValidationError(
            f"construction {construction_id} is "
            + ("not started" if chain[0].state == "prepared" else "still running")
            + ", so its tasks have no outcome to accept yet",
            code="forge_collection_not_ready",
            details={"construction_id": construction_id, "state": chain[0].state},
        )
    while (retried := chain[-1].record.review.retry_of) is not None:
        chain.append(read_construction_status(paths, retried))
    return chain


def _candidate(
    name: str, chain: list[ForgeConstructionStatus]
) -> ForgeCollectionCandidate:
    """How a task went the last time a construction in the chain tried it."""
    construction, task = _last_try(name, chain)
    package = task.package
    return ForgeCollectionCandidate(
        task_name=name,
        construction_id=construction.construction_id,
        state=task.state,
        build_id=None if package is None else package.build_id,
        usable=package is not None and package.usable_tasks > 0,
        why=_why(task),
    )


def _last_try(
    name: str, chain: list[ForgeConstructionStatus]
) -> tuple[ForgeConstructionStatus, ForgeConstructionTaskStatus]:
    """Return the newest construction in the chain that tried a task, and how."""
    return next(
        (status, task)
        for status in chain
        for task in status.tasks
        if task.task_name == name
    )


def _why(task: ForgeConstructionTaskStatus) -> str | None:
    if task.call is not None and task.call.failure is not None:
        return task.call.failure.message
    return None


class _Committed(NamedTuple):
    """One qualified task by its claim, its files and its qualification,
    before its part."""

    task_name: str
    claim: str
    kind: ForgeTaskKind
    build_id: str
    task_id: str
    content_digest: str
    fingerprint: str
    qualification_digest: str


def _commit(paths: TechtreePaths, task: ForgeConstructionTaskStatus) -> _Committed:
    """Commit one qualified task by its package's claim, its files, checked on
    disk, and its qualification."""
    package = task.package
    assert package is not None  # a qualified task's last try wrote a package
    status = read_build_status(paths, package.build_id)
    build, qualification = status.build, status.qualification
    assert build is not None and qualification is not None  # it qualified
    verify_task_set(Path(status.tasks_path), build.task_set)
    # A written package is imported as a build of exactly one task.
    [manifest] = build.task_set.tasks
    evidence = next(
        task for task in qualification.tasks if task.task_id == manifest.task_id
    )
    return _Committed(
        task_name=package.task_name,
        claim=package.claim,
        kind=package.kind,
        build_id=package.build_id,
        task_id=manifest.task_id,
        content_digest=manifest.content_digest,
        fingerprint=task_fingerprint(manifest),
        qualification_digest=digest_object(evidence),
    )


def _parent(
    paths: TechtreePaths, previous: str, source_digest: str
) -> ForgeCollectionParent:
    """Return the accepted collection a new version of the same Skill replaces."""
    status = read_collection_status(paths, previous)
    if status.acceptance is None:
        raise ValidationError(
            f"collection {previous} was never accepted, so a new version cannot "
            "replace it",
            code="forge_collection_not_accepted",
            details={"collection_id": previous},
        )
    if status.record.review.source_digest != source_digest:
        raise ValidationError(
            f"collection {previous} holds tasks of Skill "
            f"{status.record.review.source_digest[:19]}, not {source_digest[:19]}; "
            "a new version is of a Skill with the same files",
            code="forge_collection_other_source",
            details={"collection_id": previous, "source_digest": source_digest},
        )
    return ForgeCollectionParent(
        collection_id=previous,
        collection_digest=status.record.collection_digest,
        version=status.record.review.version,
        parts=status.record.review.fixed_parts(),
    )


# ---------------------------------------------------------------------------
# Reading back
# ---------------------------------------------------------------------------


def read_collection_status(
    paths: TechtreePaths, collection_id: str
) -> ForgeCollectionStatus:
    """Read a collection and its acceptance back."""
    directory = paths.forge_collection_dir(validate_id(collection_id, "forgecol"))
    if not (directory / COLLECTION_FILENAME).is_file():
        raise NotFoundError(
            f"no prepared collection {collection_id}",
            code="forge_collection_not_found",
            details={"collection_id": collection_id, "path": str(directory)},
        )
    try:
        record = ForgeCollectionRecord.model_validate_json(
            (directory / COLLECTION_FILENAME).read_bytes()
        )
        acceptance = (
            ForgeCollectionAcceptance.model_validate_json(
                (directory / ACCEPTANCE_FILENAME).read_bytes()
            )
            if (directory / ACCEPTANCE_FILENAME).is_file()
            else None
        )
    except ModelValidationError as error:
        issue = error.errors(include_input=False, include_url=False)[0]
        raise ValidationError(
            f"invalid collection evidence: {issue['msg']}",
            code="forge_evidence_invalid",
            details={"collection_id": collection_id, "path": str(directory)},
        ) from error
    state: ForgeCollectionState = "prepared" if acceptance is None else "accepted"
    return ForgeCollectionStatus(
        collection_id=collection_id,
        path=str(directory),
        state=state,
        record=record,
        acceptance=acceptance,
    )
