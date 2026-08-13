"""What a ReleaseCore is, and what makes one honest. Spec sections 6.6, 9.3.

A ReleaseCore is the single document that says which CLI, which engine, which
catalog, which Climb, and which Skills are one release. It is generated before
the CLI wheel and the plugin commit exist, which is what keeps the
cross-repository binding acyclic (spec section 9.3.3): the wheel and the plugin
embed these exact bytes, and the website's later ``BootstrapRelease`` wraps
them.

The hard problem this module solves is not the field list. It is that a release
document is written *before* the founder has chosen half of what it names — the
public CLI version, the tagged source commit, the two Skill artifacts — and a
document with plausible-looking blanks in it is worse than no document at all,
because it reads as a real release to everything downstream.

So placeholder-ness lives in the data, the way the website's bootstrap document
already states it, and three rules make the declaration impossible to get
wrong:

* every field named in ``placeholder_fields`` really does hold the one
  canonical placeholder spelling for its kind;
* every field holding that spelling is named in ``placeholder_fields``;
* ``placeholder_release`` is true exactly when there is at least one such
  field.

Together they mean a release cannot claim to be real while still carrying a
blank, and cannot be marked provisional once every coordinate is bound. A
fourth rule protects the values that are read out of this source tree rather
than chosen by a person — the protocol version, the engine, the catalog, the
introductory Climb, the subject harness — by refusing any placeholder spelling
in them at all. Those are never unknown at generation time, so a placeholder
there is a defect in the generator, not a pending decision.

There are exactly three placeholder spellings, one per kind of coordinate: a
version string, a 40-character commit, and a digest. Each is unmistakable and
none can ever collide with a real value — no release is version
``0.0.0-placeholder``, no commit is forty zeros, and no bytes hash to zero.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Final, Literal, Self

from pydantic import StringConstraints, model_validator

from techtree.constants import DIGEST_PREFIX
from techtree.models.base import Digest, NonEmptyString, ProtocolModel

__all__ = [
    "ALWAYS_BOUND_FIELDS",
    "BUILD_INFO_SCHEMA_VERSION",
    "COMMIT_PATTERN",
    "PLACEHOLDER_COMMIT",
    "PLACEHOLDER_DIGEST",
    "PLACEHOLDER_SPELLINGS",
    "PLACEHOLDER_VALUES",
    "PLACEHOLDER_VERSION",
    "RELEASE_CORE_SCHEMA_VERSION",
    "RELEASE_INPUTS_SCHEMA_VERSION",
    "Commit",
    "ReleaseCore",
    "ReleaseInputs",
    "declared_placeholder_fields",
]

RELEASE_CORE_SCHEMA_VERSION: Final = "techtree.release-core.v1"
RELEASE_INPUTS_SCHEMA_VERSION: Final = "techtree.release-inputs.v1"
BUILD_INFO_SCHEMA_VERSION: Final = "techtree.release-build-info.v1"

#: A full git commit, lowercase, never abbreviated. Spec section 9.3.2 pins
#: exact commits, and an abbreviation is not one.
COMMIT_PATTERN: Final = r"^[0-9a-f]{40}$"

type Commit = Annotated[str, StringConstraints(pattern=COMMIT_PATTERN)]

#: The one spelling of "a version nobody has chosen yet".
PLACEHOLDER_VERSION: Final = "0.0.0-placeholder"
#: The one spelling of "a commit that does not exist yet".
PLACEHOLDER_COMMIT: Final = "0" * 40
#: The one spelling of "bytes that do not exist yet". Nothing hashes to this.
PLACEHOLDER_DIGEST: Final = f"{DIGEST_PREFIX}{'0' * 64}"

#: Which ReleaseCore fields may stand unbound, and what each one looks like
#: while it does. A field that is not in here must always carry a real value.
PLACEHOLDER_SPELLINGS: Final[Mapping[str, str]] = {
    "cli_source_commit": PLACEHOLDER_COMMIT,
    "cli_version": PLACEHOLDER_VERSION,
    "maximum_tested_host_hermes_version": PLACEHOLDER_VERSION,
    "minimum_host_hermes_version": PLACEHOLDER_VERSION,
    "release_id": PLACEHOLDER_VERSION,
    "skill_improver_digest": PLACEHOLDER_DIGEST,
    "starter_skill_digest": PLACEHOLDER_DIGEST,
}

#: Every placeholder spelling, whatever field it belongs to.
PLACEHOLDER_VALUES: Final[frozenset[str]] = frozenset(PLACEHOLDER_SPELLINGS.values())

#: Read out of this source tree by the generator, so never unknown and never
#: allowed to hold a placeholder.
ALWAYS_BOUND_FIELDS: Final[tuple[str, ...]] = (
    "catalog_digest",
    "engine_digest",
    "intro_climb_reference",
    "protocol_version",
    "subject_hermes_version",
)


def declared_placeholder_fields(values: Mapping[str, str]) -> list[str]:
    """Return the placeholder-able fields whose value is still a placeholder."""
    return sorted(
        name
        for name, spelling in PLACEHOLDER_SPELLINGS.items()
        if values.get(name) == spelling
    )


class ReleaseCore(ProtocolModel):
    """The frozen coordinates of one Climb release. Spec section 6.6.

    The field list is the specification's, with one addition: the release says
    out loud whether it is a placeholder and which of its coordinates are still
    blank. Downstream repositories copy these bytes verbatim, so a reader that
    never learns to decode anything else still learns that much.
    """

    schema_version: Literal["techtree.release-core.v1"]
    placeholder_release: bool
    placeholder_fields: list[str]
    release_id: NonEmptyString
    cli_version: NonEmptyString
    cli_source_commit: Commit
    protocol_version: NonEmptyString
    engine_digest: Digest
    catalog_digest: Digest
    intro_climb_reference: NonEmptyString
    starter_skill_digest: Digest
    skill_improver_digest: Digest
    minimum_host_hermes_version: NonEmptyString
    maximum_tested_host_hermes_version: NonEmptyString
    subject_hermes_version: NonEmptyString

    @model_validator(mode="after")
    def _check_placeholder_declaration(self) -> Self:
        """Enforce the four rules that make the declaration non-forgeable."""
        declared = list(self.placeholder_fields)
        if declared != sorted(set(declared)):
            raise ValueError(
                "placeholder_fields must be sorted and must not repeat a field"
            )

        unknown = [name for name in declared if name not in PLACEHOLDER_SPELLINGS]
        if unknown:
            raise ValueError(
                "placeholder_fields names fields that have no placeholder "
                f"spelling: {unknown}"
            )

        actual = declared_placeholder_fields(
            {name: getattr(self, name) for name in PLACEHOLDER_SPELLINGS}
        )
        if declared != actual:
            raise ValueError(
                "placeholder_fields must name exactly the fields that hold a "
                f"placeholder value; it declares {declared} and the document "
                f"holds {actual}"
            )

        if self.placeholder_release != bool(actual):
            raise ValueError(
                "placeholder_release must be true exactly when a coordinate is "
                f"still a placeholder; it is {self.placeholder_release} with "
                f"{len(actual)} placeholder fields"
            )

        blank = [
            name
            for name in ALWAYS_BOUND_FIELDS
            if getattr(self, name) in PLACEHOLDER_VALUES
        ]
        if blank:
            raise ValueError(
                "these coordinates are read from the source tree and can never "
                f"be placeholders: {blank}"
            )
        return self


class ReleaseInputs(ProtocolModel):
    """The founder-owned half of a ReleaseCore. Spec section 4.5.

    Every value here is a decision a person makes and freezes — the published
    version, the tagged commit, the Skill artifacts, the host Hermes range.
    None of them can be derived from this repository, so they are held in one
    hand-edited file that the generator reads, rather than passed as command
    options that would leave the generated document unreproducible.

    The remaining ReleaseCore coordinates are absent on purpose. A release
    input file that tried to state the engine digest or the protocol version
    would be asserting something the source tree already answers.
    """

    schema_version: Literal["techtree.release-inputs.v1"]
    release_id: NonEmptyString
    cli_version: NonEmptyString
    cli_source_commit: Commit
    intro_climb_reference: NonEmptyString
    starter_skill_digest: Digest
    skill_improver_digest: Digest
    minimum_host_hermes_version: NonEmptyString
    maximum_tested_host_hermes_version: NonEmptyString
