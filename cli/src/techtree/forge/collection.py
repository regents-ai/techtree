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

Verifying an accepted collection makes its review again from what is on disk
now: every member's files are hashed against their build's commitment, every
qualification is read back, and the digest must be the one accepted. Anything
else is refused as a changed collection.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from pydantic import ValidationError as ModelValidationError

from techtree.canonical import digest_object
from techtree.errors import ConflictError, NotFoundError, TechtreeError, ValidationError
from techtree.forge.authoring import AnsweredWith, ReviewedOn
from techtree.forge.construction import read_construction_status
from techtree.forge.content import verify_task_set
from techtree.forge.models import (
    FORGE_COLLECTION_ACCEPTANCE_SCHEMA_VERSION,
    FORGE_COLLECTION_SCHEMA_VERSION,
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
)
from techtree.forge.planning import read_proposal_status
from techtree.forge.service import read_build_status
from techtree.fs import atomic_write_json
from techtree.ids import new_id, validate_id
from techtree.paths import TechtreePaths

__all__ = [
    "accept_collection",
    "check_collection",
    "prepare_collection",
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
    members = [_member(paths, by_name[name]) for name in names]
    parent = None if previous is None else _parent(paths, previous, newest.source_id)
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
        source_id=newest.source_id,
        source_digest=newest.source_digest,
        constructions=[status.construction_id for status in chain],
        previous=parent,
        version=1 if parent is None else parent.version + 1,
        tasks=candidates,
        members=members,
        membership_digest=digest_object(members),
    )


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
    construction, task = next(
        (status, task)
        for status in chain
        for task in status.tasks
        if task.task_name == name
    )
    package = task.package
    return ForgeCollectionCandidate(
        task_name=name,
        construction_id=construction.construction_id,
        state=task.state,
        build_id=None if package is None else package.build_id,
        usable=package is not None and package.usable_tasks > 0,
        why=_why(task),
    )


def _why(task: ForgeConstructionTaskStatus) -> str | None:
    if task.call is not None and task.call.failure is not None:
        return task.call.failure.message
    return None


def _member(
    paths: TechtreePaths, candidate: ForgeCollectionCandidate
) -> ForgeCollectionMember:
    """Commit one qualified task by its files, checked on disk, and qualification."""
    assert candidate.build_id is not None  # a usable candidate names its build
    status = read_build_status(paths, candidate.build_id)
    build, qualification = status.build, status.qualification
    assert build is not None and qualification is not None  # it qualified
    verify_task_set(Path(status.tasks_path), build.task_set)
    # A written package is imported as a build of exactly one task.
    [manifest] = build.task_set.tasks
    evidence = next(
        task for task in qualification.tasks if task.task_id == manifest.task_id
    )
    return ForgeCollectionMember(
        task_name=candidate.task_name,
        build_id=candidate.build_id,
        task_id=manifest.task_id,
        content_digest=manifest.content_digest,
        qualification_digest=digest_object(evidence),
    )


def _parent(
    paths: TechtreePaths, previous: str, source_id: str
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
    if status.record.review.source_id != source_id:
        raise ValidationError(
            f"collection {previous} holds tasks of Skill "
            f"{status.record.review.source_id}, not {source_id}; a new version "
            "is of the same Skill",
            code="forge_collection_other_source",
            details={"collection_id": previous, "source_id": source_id},
        )
    return ForgeCollectionParent(
        collection_id=previous,
        collection_digest=status.record.collection_digest,
        version=status.record.review.version,
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
