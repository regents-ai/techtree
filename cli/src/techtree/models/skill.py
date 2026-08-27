"""Candidate skills and the draft that submits them. Spec 11.7, decisions 0003.

A ``SkillArtifact`` is the content-addressed description of what a participant
wrote: the files, their digests, and the digest of the tree as a whole. No
local path ever enters it, because a draft that recorded where a skill lived on
one machine would not be reproducible on another and would leak the author's
directory layout into a public object.

A ``SubmissionDraft`` is the complete, reviewable statement of what is about to
be run, including the rights the participant is being asked to accept.
Decisions document 0003 A5 splits that from the moment of accepting: the draft
carries a ``PolicyAcceptanceRequirement`` — the digest, whether acceptance is
required, and a stable human-readable summary — while the acknowledgement
itself is recorded on the ``RunRequest``. Stating what will have to be accepted
and recording that it was accepted are two different facts, and the two objects
keep them from being blurred.
"""

from __future__ import annotations

from typing import Final, Literal, Self

from pydantic import Field, model_validator

from techtree.models.base import (
    Digest,
    NonEmptyString,
    ProtocolModel,
    UtcDateTime,
)
from techtree.models.campaign import ProgramRef, PublicContext

__all__ = [
    "SKILL_ENTRY_FILE",
    "PolicyAcceptanceRequirement",
    "SkillArtifact",
    "SkillFile",
    "SubmissionDraft",
]

#: The one file every instruction skill must contain. Its absence is not a
#: warning: a skill with no instructions is not a skill.
SKILL_ENTRY_FILE: Final = "SKILL.md"


def _check_relative_posix_path(value: str) -> None:
    """Raise when a path is absolute, escaping, or not POSIX-spelled."""
    if value != value.strip():
        raise ValueError(f"skill path has surrounding whitespace: {value!r}")
    if value.startswith("/") or (len(value) > 1 and value[1] == ":"):
        raise ValueError(f"skill paths are relative; got {value!r}")
    if "\\" in value:
        raise ValueError(f"skill paths use forward slashes; got {value!r}")
    segments = value.split("/")
    if any(segment in ("", ".", "..") for segment in segments):
        raise ValueError(f"skill path is not a normalized relative path: {value!r}")


class SkillFile(ProtocolModel):
    """One file inside a skill, addressed by content."""

    path: NonEmptyString
    media_type: NonEmptyString
    size: int = Field(ge=0)
    digest: Digest

    @model_validator(mode="after")
    def _check_path(self) -> Self:
        """Reject anything that is not a normalized relative POSIX path."""
        _check_relative_posix_path(self.path)
        return self


class SkillArtifact(ProtocolModel):
    """A complete candidate skill, addressed by content."""

    schema_version: Literal["techtree.skill.v1alpha1"]
    name: NonEmptyString
    root_digest: Digest
    archive_digest: Digest
    files: list[SkillFile]
    source_kind: Literal["manual"]
    parent_skill_digest: Digest | None

    @model_validator(mode="after")
    def _check_file_list(self) -> Self:
        """Require the entry file, a stable order, and no repeated path."""
        paths = [file.path for file in self.files]
        if SKILL_ENTRY_FILE not in paths:
            raise ValueError(f"a skill must contain {SKILL_ENTRY_FILE}")
        if len(set(paths)) != len(paths):
            raise ValueError("a skill lists each path exactly once")
        if paths != sorted(paths):
            raise ValueError(
                "skill files are sorted by path so that the same tree always "
                "produces the same digest"
            )
        return self


class PolicyAcceptanceRequirement(ProtocolModel):
    """The rights policy a participant is being asked to accept.

    Decisions document 0003 A5. This states what must be accepted; it does not
    record that anyone accepted it.
    """

    data_policy_digest: Digest
    required: bool
    summary: NonEmptyString


class SubmissionDraft(ProtocolModel):
    """Everything a participant is about to commit to, in one object."""

    schema_version: Literal["techtree.submission-draft.v1alpha1"]
    id: NonEmptyString
    campaign_spec_digest: Digest
    program_ref: ProgramRef | None
    public_context: PublicContext | None
    data_policy_digest: Digest
    outcome_contract_digest: Digest | None
    skill_artifact: SkillArtifact
    baseline_manifest_digest: Digest
    candidate_manifest_digest: Digest
    included_files: list[NonEmptyString]
    estimated_episodes: int = Field(ge=1)
    policy_acceptance: PolicyAcceptanceRequirement
    warnings: list[NonEmptyString]
    created_at: UtcDateTime

    @model_validator(mode="after")
    def _check_draft(self) -> Self:
        """Keep the draft self-consistent about rights, files, and variants."""
        if self.policy_acceptance.data_policy_digest != self.data_policy_digest:
            raise ValueError(
                "the draft asks for acceptance of a different DataPolicy than "
                "the one it runs under"
            )
        if self.baseline_manifest_digest == self.candidate_manifest_digest:
            raise ValueError(
                "baseline and candidate manifests must differ; an identical "
                "pair measures nothing"
            )
        for path in self.included_files:
            _check_relative_posix_path(path)
        if self.included_files != sorted(self.included_files):
            raise ValueError("included_files is sorted")
        if len(set(self.included_files)) != len(self.included_files):
            raise ValueError("included_files lists each path exactly once")
        artifact_paths = [file.path for file in self.skill_artifact.files]
        if self.included_files != artifact_paths:
            raise ValueError(
                "included_files must be exactly the files in the skill artifact"
            )
        return self
