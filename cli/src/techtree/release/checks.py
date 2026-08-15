"""Whether one release still agrees with itself. Spec sections 9.5 and 9.7.

A ReleaseCore is a set of claims about things that live elsewhere: an engine
bundle, a catalog index, an installed package, a Climb, two Skills. Each
claim is checked here against the thing it names, one check per claim, so that
a failure says which coordinate drifted rather than that "the release is
broken".

Two verdicts are not enough. A check that could not run is not a check that
passed, and reporting it as one is how a release ships with something nobody
looked at. So a check is ``passed``, ``failed``, or ``skipped``, and a
verification is verified when nothing failed — with every skip still visible in
the output, named and explained.

Two coordinates cannot be settled from inside an installed CLI at all: the two
founder Skill digests, whose bytes live with the plugin and the website, and
the address the starter Skill is published at, which a verification that
contacts nothing must not go and fetch. Those are reported as skips with their
values in the detail, so a reader sees the coordinate and sees that nobody
here checked it.

Every coordinate a release names is a real one (decisions 0026), so there is
nothing here that treats a value as provisional: a document that parsed is a
document whose every coordinate was chosen, and each one is compared against
the thing it names.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Literal, Self

from pydantic import model_validator

from techtree.catalog.repository import EmbeddedCatalogRepository
from techtree.engines.bundle import engine_bundle_digest
from techtree.errors import ValidationError
from techtree.models.base import Digest, NonEmptyString, ProtocolModel
from techtree.release.document import (
    document_digest,
    is_canonical_document,
    parse_release_core,
)
from techtree.release.generate import ReleaseSources
from techtree.release.models import ReleaseCore
from techtree.version import package_version

__all__ = [
    "RELEASE_COORDINATE_MISMATCH",
    "RELEASE_CORE_DIGEST_MISMATCH",
    "RELEASE_CORE_INVALID",
    "RELEASE_CORE_NOT_CANONICAL",
    "ReleaseCheck",
    "ReleaseFacts",
    "ReleaseVerification",
    "local_release_facts",
    "verify_release_core",
]

#: Stable failure codes. A caller branches on these, never on wording.
RELEASE_CORE_INVALID: Final = "release_core_invalid"
RELEASE_CORE_NOT_CANONICAL: Final = "release_core_not_canonical"
RELEASE_CORE_DIGEST_MISMATCH: Final = "release_core_digest_mismatch"
RELEASE_COORDINATE_MISMATCH: Final = "release_coordinate_mismatch"

#: Why a check could not be run. Never a failure and never a pass.
RELEASE_CHECK_NOT_APPLICABLE: Final = "release_check_not_applicable"

type ReleaseCheckStatus = Literal["passed", "failed", "skipped"]


class ReleaseCheck(ProtocolModel):
    """One named claim, and what comparing it against reality found."""

    id: NonEmptyString
    status: ReleaseCheckStatus
    code: NonEmptyString
    detail: NonEmptyString


class ReleaseVerification(ProtocolModel):
    """Every check a release verification ran, and its single verdict."""

    verified: bool
    checks: list[ReleaseCheck]

    @property
    def failures(self) -> list[ReleaseCheck]:
        """Return every check that failed."""
        return [check for check in self.checks if check.status == "failed"]

    @property
    def skipped(self) -> list[ReleaseCheck]:
        """Return every check that could not be run."""
        return [check for check in self.checks if check.status == "skipped"]

    @model_validator(mode="after")
    def _check_verdict_follows_the_checks(self) -> Self:
        """Refuse a verdict the checks do not support."""
        if self.verified != (not self.failures):
            raise ValueError(
                "a release verifies exactly when no check failed; this one "
                f"claims verified={self.verified} with {len(self.failures)} "
                "failed checks"
            )
        return self


@dataclass(frozen=True)
class ReleaseFacts:
    """What this machine and this source tree actually contain.

    Plain values rather than live objects, so that a verification is a pure
    comparison and a test can break exactly one fact at a time.
    """

    package_version: str
    protocol_version: str
    engine_digest: Digest
    catalog_digest: Digest
    climb_references: tuple[str, ...]
    subject_hermes_versions: Mapping[str, str]


def local_release_facts(sources: ReleaseSources) -> ReleaseFacts:
    """Read the facts a release is checked against out of one source tree."""
    catalog = EmbeddedCatalogRepository(sources.catalog_root)
    references = tuple(catalog.list_climb_references())
    harnesses: dict[str, str] = {}
    for reference in references:
        climb = catalog.load_climb(reference)
        campaign = catalog.load_campaign(climb.campaign_spec_digest)
        harnesses[reference] = campaign.subject.harness.version

    return ReleaseFacts(
        package_version=package_version(),
        protocol_version=sources.protocol_version,
        engine_digest=engine_bundle_digest(sources.engine_root),
        catalog_digest=document_digest(sources.catalog_index_bytes()),
        climb_references=references,
        subject_hermes_versions=harnesses,
    )


def verify_release_core(
    raw: bytes,
    facts: ReleaseFacts,
    *,
    expected_digest: Digest | None = None,
) -> ReleaseVerification:
    """Check a stored ReleaseCore against the build it claims to describe."""
    checks = [_document_check(raw)]
    if checks[0].status == "failed":
        # Nothing below can be compared against a document that is not one.
        return _verification(checks)

    core = parse_release_core(raw)
    checks.extend(
        [
            _canonical_bytes_check(raw),
            _digest_check(raw, expected_digest),
            _cli_version_check(core, facts),
            _protocol_version_check(core, facts),
            _engine_digest_check(core, facts),
            _catalog_digest_check(core, facts),
            _intro_climb_check(core, facts),
            _subject_hermes_check(core, facts),
            *_founder_skill_checks(core),
            _starter_skill_source_check(core),
        ]
    )
    return _verification(checks)


# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------


def _document_check(raw: bytes) -> ReleaseCheck:
    try:
        core = parse_release_core(raw)
    except ValidationError as error:
        return _failed("release_core_document", RELEASE_CORE_INVALID, str(error))

    return _passed(
        "release_core_document",
        f"the ReleaseCore is valid: release {core.release_id}, with every "
        "coordinate concrete.",
    )


def _canonical_bytes_check(raw: bytes) -> ReleaseCheck:
    if is_canonical_document(raw):
        return _passed(
            "release_core_canonical_bytes",
            "the stored bytes are in the one published spelling.",
        )
    return _failed(
        "release_core_canonical_bytes",
        RELEASE_CORE_NOT_CANONICAL,
        "the stored bytes are not in the published spelling, so their digest "
        "is not the digest the generator would produce; regenerate rather "
        "than edit this file.",
    )


def _digest_check(raw: bytes, expected: Digest | None) -> ReleaseCheck:
    actual = document_digest(raw)
    if expected is None:
        return _skipped(
            "release_core_digest",
            f"no expected digest was given; these bytes are {actual}.",
        )
    if actual == expected:
        return _passed(
            "release_core_digest",
            f"the embedded ReleaseCore is {actual}, as expected.",
        )
    return _failed(
        "release_core_digest",
        RELEASE_CORE_DIGEST_MISMATCH,
        f"the embedded ReleaseCore is {actual}, not the expected {expected}.",
    )


def _cli_version_check(core: ReleaseCore, facts: ReleaseFacts) -> ReleaseCheck:
    if core.cli_version == facts.package_version:
        return _passed(
            "cli_version",
            f"the installed package is {facts.package_version}, the version "
            "this release names.",
        )
    return _failed(
        "cli_version",
        RELEASE_COORDINATE_MISMATCH,
        f"this release names CLI version {core.cli_version}, but the "
        f"installed package is {facts.package_version}.",
    )


def _protocol_version_check(core: ReleaseCore, facts: ReleaseFacts) -> ReleaseCheck:
    return _equality(
        "protocol_version",
        claimed=core.protocol_version,
        actual=facts.protocol_version,
        subject="the protocol version",
    )


def _engine_digest_check(core: ReleaseCore, facts: ReleaseFacts) -> ReleaseCheck:
    return _equality(
        "engine_digest",
        claimed=core.engine_digest,
        actual=facts.engine_digest,
        subject="the managed engine bundle",
    )


def _catalog_digest_check(core: ReleaseCore, facts: ReleaseFacts) -> ReleaseCheck:
    return _equality(
        "catalog_digest",
        claimed=core.catalog_digest,
        actual=facts.catalog_digest,
        subject="the catalog index",
    )


def _intro_climb_check(core: ReleaseCore, facts: ReleaseFacts) -> ReleaseCheck:
    if core.intro_climb_reference in facts.climb_references:
        return _passed(
            "intro_climb_reference",
            f"this build ships {core.intro_climb_reference}, the introductory "
            "Climb the release names.",
        )
    return _failed(
        "intro_climb_reference",
        RELEASE_COORDINATE_MISMATCH,
        f"this release leads with {core.intro_climb_reference}, which this "
        f"build does not ship; it ships {list(facts.climb_references)}.",
    )


def _subject_hermes_check(core: ReleaseCore, facts: ReleaseFacts) -> ReleaseCheck:
    pinned = facts.subject_hermes_versions.get(core.intro_climb_reference)
    if pinned is None:
        return _failed(
            "subject_hermes_version",
            RELEASE_COORDINATE_MISMATCH,
            "the subject harness version cannot be compared because this "
            f"build ships no Climb called {core.intro_climb_reference}.",
        )
    return _equality(
        "subject_hermes_version",
        claimed=core.subject_hermes_version,
        actual=pinned,
        subject="the subject harness the introductory Campaign pins",
    )


def _founder_skill_checks(core: ReleaseCore) -> list[ReleaseCheck]:
    """Report each founder Skill digest, which this package cannot resolve.

    The CLI ships no Skill bytes — the starter Skill is served by the website
    and the operator Skill is bundled by the plugin — so each digest is checked
    where those bytes are, not here (spec section 9.6).
    """
    return [
        _skipped(
            field,
            f"this release binds {field.removesuffix('_digest')} to "
            f"{getattr(core, field)}; the CLI package carries no Skill bytes, "
            "so the plugin and the website verify it against the Skill they "
            "serve.",
        )
        for field in ("starter_skill_digest", "skill_improver_digest")
    ]


def _starter_skill_source_check(core: ReleaseCore) -> ReleaseCheck:
    """Report where the starter Skill is published, without going to look.

    ``release verify`` contacts nothing, which is the property that lets a host
    agent run it on a machine that has just been installed and may not be
    online. So a bound address is reported rather than resolved: what the bytes
    at the other end have to be is already settled by the digest beside it, and
    that comparison happens where the fetch does (spec section 10.5).
    """
    return _skipped(
        "starter_skill_object_url",
        f"this release publishes the starter Skill at "
        f"{core.starter_skill_object_url}; nothing is fetched here, and what "
        "is served is checked against the digest when it is obtained.",
    )


# ---------------------------------------------------------------------------
# Building checks
# ---------------------------------------------------------------------------


def _equality(
    identifier: str, *, claimed: str, actual: str, subject: str
) -> ReleaseCheck:
    if claimed == actual:
        return _passed(identifier, f"{subject} is {actual}, as the release says.")
    return _failed(
        identifier,
        RELEASE_COORDINATE_MISMATCH,
        f"the release says {subject} is {claimed}; it is {actual}.",
    )


def _passed(identifier: str, detail: str) -> ReleaseCheck:
    return ReleaseCheck(id=identifier, status="passed", code="ok", detail=detail)


def _failed(identifier: str, code: str, detail: str) -> ReleaseCheck:
    return ReleaseCheck(id=identifier, status="failed", code=code, detail=detail)


def _skipped(identifier: str, detail: str) -> ReleaseCheck:
    return ReleaseCheck(
        id=identifier,
        status="skipped",
        code=RELEASE_CHECK_NOT_APPLICABLE,
        detail=detail,
    )


def _verification(checks: list[ReleaseCheck]) -> ReleaseVerification:
    return ReleaseVerification(
        verified=not any(check.status == "failed" for check in checks),
        checks=checks,
    )
