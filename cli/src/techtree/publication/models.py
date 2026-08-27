"""What is sent, and what comes back. Decisions document 0038.

Two documents cross the one boundary this package opens, and they are separate
objects because they are made by different parties and prove different things.

A :class:`PublicationSubmission` is what the participant sends: the proof
directory, file by file, exactly as it sits on disk. Nothing is summarised,
nothing is re-derived, and nothing is added — the bundle already commits to
every one of those files by digest under the participant's own signature, so
sending anything but the stored bytes would be sending something nobody signed.
It carries no episodes and no transcripts, because the proof directory holds
none: an episode receipt carries digests, task hashes and scores, and the raw
episodes live outside the directory entirely.

A :class:`PublicationReceipt` is what the network sends back: where the entry
landed in the log, which bundle it accepted, when, and which of its own checks
it ran. The participant signed their run and the network countersigns that it
accepted it, which is what makes an accepted entry checkable by somebody who
trusts neither party's word about the other.

The one field that is neither is the contributor address. It is optional, it is
volunteered, and its name says it is unverified, because a string somebody typed
is not proof of control of an account. It travels in the submission body and is
kept nowhere on this machine.
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from techtree.models.base import (
    Digest,
    NonEmptyString,
    ProtocolModel,
    PublicKeyRef,
    SignatureEnvelope,
    UtcDateTime,
)

__all__ = [
    "PublicationCheck",
    "PublicationReceipt",
    "PublicationSubmission",
    "SubmittedFile",
]


class SubmittedFile(ProtocolModel):
    """One file of the proof directory, placed and carried verbatim."""

    #: Where the file sits inside the proof directory, in POSIX spelling. It is
    #: the same string the bundle manifest places the file under, so the
    #: receiving side can check each file against the manifest it arrived with.
    path: NonEmptyString
    digest: Digest
    size: int = Field(gt=0)
    #: The file's bytes, base64 encoded. Every file in a proof bundle is
    #: canonical JSON, and base64 is what carries bytes through JSON without a
    #: second encoding decision.
    content: NonEmptyString


class PublicationSubmission(ProtocolModel):
    """Everything one publication sends, and nothing else."""

    schema_version: Literal["techtree.publication-submission.v1alpha1"]
    run_id: NonEmptyString
    #: The digest of the bundle's own signed manifest, which commits to every
    #: file below. One value identifies the whole submission.
    bundle_digest: Digest
    files: list[SubmittedFile]
    #: An address somebody chose to leave, in its canonical lowercase form.
    #: The name is the record: nothing here proves the sender controls it.
    contributor_address_unverified: NonEmptyString | None = None

    @model_validator(mode="after")
    def _check_the_files_are_a_bundle(self) -> Self:
        """Reject a submission that places no file, or one file twice."""
        if not self.files:
            raise ValueError("a publication submits at least one file")
        paths = [entry.path for entry in self.files]
        if len(set(paths)) != len(paths):
            raise ValueError("a publication places each file exactly once")
        return self


class PublicationCheck(ProtocolModel):
    """One check the network ran on a submission, and how it came out."""

    id: NonEmptyString
    passed: bool
    detail: NonEmptyString


class PublicationReceipt(ProtocolModel):
    """The network's countersigned record that it accepted one submission."""

    schema_version: Literal["techtree.publication-receipt.v1alpha1"]
    id: NonEmptyString
    run_id: NonEmptyString
    #: Where this entry sits in the log. The log is ordered by arrival and by
    #: nothing else, so this is a position in time rather than a rank.
    log_sequence: int = Field(ge=0)
    bundle_digest: Digest
    accepted_at: UtcDateTime
    checks: list[PublicationCheck]
    #: Where the entry can now be read.
    entry_url: NonEmptyString
    #: The network's own key and its signature over this receipt's digest. They
    #: are carried so that the receipt can be checked later by anybody holding
    #: the network's published public half, including by somebody who was not
    #: party to the exchange.
    public_key: PublicKeyRef
    signature: SignatureEnvelope

    @model_validator(mode="after")
    def _check_the_receipt_reports_its_own_checks(self) -> Self:
        """Reject a receipt that accepted a submission it never checked."""
        if not self.checks:
            raise ValueError("a publication receipt names the checks that ran")
        identifiers = [check.id for check in self.checks]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("a publication receipt reports each check once")
        return self

    @property
    def failed_checks(self) -> list[PublicationCheck]:
        """Return every check the network ran and did not pass."""
        return [check for check in self.checks if not check.passed]
