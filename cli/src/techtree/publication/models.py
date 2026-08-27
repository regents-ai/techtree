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

The submission is a mapping of path to bytes and it has exactly four members,
which decisions 0038's wire contract fixes so that the two halves of this
feature cannot drift. Both of those shapes are refusals rather than
preferences, and each is written into the model below beside the field it
constrains.

A :class:`PublicationReceipt` is what the network sends back: where the entry
landed in the log, which bundle it accepted, when, and which of its own checks
it ran. The participant signed their run and the network countersigns that it
accepted it, which is what makes an accepted entry checkable by somebody who
trusts neither party's word about the other.

The one field that is neither is the contributor address. It is optional, it is
volunteered, and its name says it is unverified, because a string somebody typed
is not proof of control of an account. It travels in the
``x-techtree-contributor-address`` header, beside the submission and never
inside it, because the run log serves a stored submission back at a public
address. It is kept nowhere on this machine.
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from techtree.models.base import (
    Base64String,
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
]


class PublicationSubmission(ProtocolModel):
    """Everything one publication sends, and nothing else.

    Four members, fixed by decisions 0038 and by nothing else. The document is
    stored by the run log and served back at a public address, so a member that
    arrived here without being in the contract would be published without
    anybody having agreed to publish it. The receiving side refuses a body that
    carries more; ``extra="forbid"`` on :class:`~techtree.models.base.
    ProtocolModel` means this side cannot build one.
    """

    schema_version: Literal["techtree.publication-submission.v1alpha1"]
    run_id: NonEmptyString
    #: The digest of the bundle's own signed manifest, which commits to every
    #: file below. One value identifies the whole submission.
    bundle_digest: Digest
    #: Where each file sits inside the proof directory, in POSIX spelling,
    #: against the base64 of its bytes. The key is the same string the bundle
    #: manifest places the file under, so the receiving side can find each file
    #: in the manifest that arrived with it.
    #:
    #: A mapping, and deliberately nothing richer. An earlier shape put a
    #: digest and a size beside each file's content, and both were the
    #: submitter's own claims about the submitter's own bytes: worth nothing if
    #: honest and dangerous if believed. Every digest and every length the
    #: receiving side works with has to come from the bundle's own signed
    #: manifest, which is inside this mapping under ``bundle.json`` and is
    #: signed by the key the bundle carries. Sending a digest beside the
    #: content invites somebody downstream to trust it instead, and the only
    #: reliable way to stop that is to have none to trust. Base64 because every
    #: file in a proof bundle is canonical JSON, and base64 is what carries
    #: bytes through JSON without a second encoding decision.
    files: dict[NonEmptyString, Base64String]

    @model_validator(mode="after")
    def _check_the_files_are_a_bundle(self) -> Self:
        """Reject a submission that places no file.

        A mapping cannot place one file twice, which is the second reason the
        contract chose one: the shape refuses a whole class of malformed
        submission rather than a validator having to notice it.
        """
        if not self.files:
            raise ValueError("a publication submits at least one file")
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
