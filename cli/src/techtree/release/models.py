"""What a ReleaseCore is, and what makes one honest. Spec sections 6.6, 9.3.

A ReleaseCore is the single document that says which CLI, which engine, which
catalog, which Climb, and which Skills are one release. It is generated before
the CLI wheel and the plugin commit exist, which is what keeps the
cross-repository binding acyclic (spec section 9.3.3): the wheel and the plugin
embed these exact bytes, and the website's later ``BootstrapRelease`` wraps
them.

Decisions document 0026 settles what may be in it. A ReleaseCore is a
*contract*: it holds only values a person can know when they author it, so it
is honestly final the moment it is committed. It therefore says nothing about
the artifact built from it — no wheel hash, no plugin commit, and no source
commit, because an artifact never describes its own identity. Identity is
stamped onto the wheel at build time (:mod:`techtree.release.provenance`) and
witnessed externally by the website's bootstrap document.

Every coordinate here is concrete, and the schema is what makes that true
rather than a convention anyone has to remember. A version is three numbers, a
release identifier is a name, a digest is sixty-four hexadecimal characters
that are not all zero, and the starter Skill's address is a content address
ending in the digest of the bytes it returns. None of those admit a spelling
that means "nobody has chosen this yet", so a document that validates is a
document whose every coordinate was chosen.
"""

from __future__ import annotations

import base64
import re
from typing import Annotated, Final, Literal, Self

from pydantic import AfterValidator, StringConstraints, model_validator

from techtree.canonical import sha256_digest_bytes
from techtree.constants import DIGEST_PREFIX
from techtree.crypto import ED25519_PUBLIC_KEY_BYTES
from techtree.models.base import Digest, NonEmptyString, ProtocolModel, PublicKeyRef

__all__ = [
    "BUILD_INFO_SCHEMA_VERSION",
    "CONCRETE_DIGEST_LENGTH",
    "CONCRETE_DIGEST_PATTERN",
    "OBJECT_URL_PATTERN",
    "PLAIN_HTTPS_URL_PATTERN",
    "RELEASE_CORE_SCHEMA_VERSION",
    "RELEASE_ID_PATTERN",
    "RELEASE_INPUTS_SCHEMA_VERSION",
    "VERSION_PATTERN",
    "ConcreteDigest",
    "ObjectUrl",
    "PinnedNetworkKey",
    "PlainHttpsUrl",
    "PublicationCoordinates",
    "ReleaseCore",
    "ReleaseId",
    "ReleaseInputs",
    "Version",
    "object_url_digest",
]

RELEASE_CORE_SCHEMA_VERSION: Final = "techtree.release-core.v1"
RELEASE_INPUTS_SCHEMA_VERSION: Final = "techtree.release-inputs.v1"
BUILD_INFO_SCHEMA_VERSION: Final = "techtree.release-build-info.v1"

#: A published version is three numbers. Everything this release names — the
#: CLI, the host Hermes range, the subject harness — is versioned that way, and
#: nothing that is merely *proposed* has a version at all, so the pattern needs
#: no room for a suffix that would let one read as the other.
VERSION_PATTERN: Final = r"^[0-9]+(?:\.[0-9]+){2}$"

type Version = Annotated[str, StringConstraints(pattern=VERSION_PATTERN)]

#: A release identifier is a name a person gives one release — ``climb-v0.1.0``
#: — so it begins with a letter and joins lowercase words with ``-`` or ``.``.
#: A bare number is a version, and a version is not an identity.
RELEASE_ID_PATTERN: Final = r"^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$"

type ReleaseId = Annotated[str, StringConstraints(pattern=RELEASE_ID_PATTERN)]

#: Sixty-four hexadecimal characters with at least one of them non-zero. The
#: length is fixed by :data:`CONCRETE_DIGEST_LENGTH` beside it, so this pattern
#: only has to say "not all zeros": nothing hashes to zero, so a zeroed digest
#: is never a measurement.
CONCRETE_DIGEST_PATTERN: Final = rf"^{DIGEST_PREFIX}0*[1-9a-f][0-9a-f]*$"
CONCRETE_DIGEST_LENGTH: Final = len(DIGEST_PREFIX) + 64

type ConcreteDigest = Annotated[
    str,
    StringConstraints(
        pattern=CONCRETE_DIGEST_PATTERN,
        min_length=CONCRETE_DIGEST_LENGTH,
        max_length=CONCRETE_DIGEST_LENGTH,
    ),
]

#: Where a published artifact is served from. Spec section 4.1 requires the
#: starter Skill to be an exact read-only object URL, and decision 0007 R10
#: requires every coordinate of a real release to be concrete and immutable, so
#: this is an absolute ``https`` content address: it ends in the digest of the
#: bytes it returns, which is how the website files public objects and how a
#: fetcher checks a response before it has scanned anything.
#:
#: The authority may not carry userinfo. A published coordinate is copied into
#: the plugin, into the website, into an approval packet and into support
#: transcripts, and ``https://user:token@host/…`` would carry a credential
#: through every one of them — while also making the address mean different
#: things to different readers. A public read-only object needs no credential,
#: so an address that offers one is not the coordinate this field is for.
OBJECT_URL_PATTERN: Final = rf"^https://[^\s/@]+/[^\s]*{DIGEST_PREFIX}[0-9a-f]{{64}}$"


def _require_resolvable_host(value: str) -> str:
    """Reject an address under a top-level domain that can never resolve.

    RFC 2606 reserves ``.invalid`` so that names under it are guaranteed not to
    resolve. An address nothing can ever fetch is not a place something is
    published, whatever else it looks like.
    """
    authority = value.removeprefix("https://").split("/", 1)[0]
    host = authority.rsplit(":", 1)[0] if ":" in authority else authority
    if host.lower().endswith(".invalid"):
        raise ValueError("an address under .invalid can never resolve")
    return value


type ObjectUrl = Annotated[
    str,
    StringConstraints(pattern=OBJECT_URL_PATTERN),
    AfterValidator(_require_resolvable_host),
]


_OBJECT_URL_DIGEST_RE: Final = re.compile(rf"{DIGEST_PREFIX}[0-9a-f]{{64}}$")


def object_url_digest(url: str) -> Digest:
    """Return the file digest a content address is keyed by.

    The address ends in the digest of the bytes it serves, which is what makes
    it safe to fetch from at all: whatever arrives is checked against the
    address it came from before anything else looks at it.

    Raises:
        ValueError: when the address ends in no digest, and therefore promises
            nothing about what it serves.
    """
    found = _OBJECT_URL_DIGEST_RE.search(url)
    if found is None:
        raise ValueError(f"{url!r} is not keyed by the digest of what it serves")
    return found.group()


#: A published address with nothing after its path. Every URL a release pins is
#: read by a machine and printed to a person, so it is ``https`` and it carries
#: no query string and no fragment: a submission travels in a request body and
#: never in a URL, and an address that could carry one would be a place a proof
#: or a volunteered address could end up in somebody's access log.
PLAIN_HTTPS_URL_PATTERN: Final = r"^https://[^\s/@?#]+(?:/[^\s?#]*)?$"

type PlainHttpsUrl = Annotated[
    str,
    StringConstraints(pattern=PLAIN_HTTPS_URL_PATTERN),
    AfterValidator(_require_resolvable_host),
]


class PinnedNetworkKey(PublicKeyRef):
    """The public half of the key the run log countersigns receipts with.

    Requiring a receipt to carry a key and a signature proves nothing on its
    own: a server that wanted to lie would invent a key, sign with it, and hand
    both to the participant. What makes a countersignature worth having is that
    the participant already knows which key to expect, so the key is pinned in
    the release rather than learned from the answer.

    The identifier is the digest of the public key and is checked to be, as
    every other key identifier in this protocol is (decisions 0038, founder
    ruling of 2026-08-27). A derived identifier cannot name one key and carry
    another, so a receipt that names a key it does not carry is caught without
    anybody writing a check for it. Rotation is a new key and therefore a new
    identifier, and a release pins exactly the one it trusts.

    Only the public half ever reaches this repository. Nothing here can sign,
    and nothing here is a place a private key could be put.
    """

    @model_validator(mode="after")
    def _check_the_identifier_is_the_digest_of_the_key(self) -> Self:
        """Reject a key whose identifier was assigned rather than derived."""
        raw = base64.b64decode(self.public_key, validate=True)
        if len(raw) != ED25519_PUBLIC_KEY_BYTES:
            raise ValueError(
                f"an Ed25519 public key is {ED25519_PUBLIC_KEY_BYTES} raw bytes"
            )
        if not any(raw):
            raise ValueError(
                "an all-zero public key names no key; it is the spelling of a "
                "coordinate nobody has chosen yet, and a release pins only "
                "coordinates somebody chose"
            )
        derived = sha256_digest_bytes(raw)
        if self.key_id != derived:
            raise ValueError(
                f"a network key identifier is the digest of the key it carries: "
                f"this one says {self.key_id} and carries {derived}"
            )
        return self


class PublicationCoordinates(ProtocolModel):
    """Where a run is published, where it is then read, and who countersigns.

    All three are release coordinates rather than settings, for one reason each
    (decisions 0038, founder ruling of 2026-08-27).

    ``submission_endpoint`` is pinned because a stable release has to be able to
    publish with nothing configured. An address that only arrived from the
    environment meant a published wheel could not publish out of the box, and a
    person who had to set a variable before publishing would be a person who
    could set it to the wrong thing.

    ``public_log_url`` is pinned because a receipt names where the entry now
    lives, and an entry address the participant did not already expect is an
    address the answering server chose. The receipt's address is checked to be
    on this origin before the receipt is written down.

    ``network_key`` is pinned because a countersignature is only worth the
    prior knowledge of which key made it.
    """

    submission_endpoint: PlainHttpsUrl
    public_log_url: PlainHttpsUrl
    network_key: PinnedNetworkKey


class ReleaseCore(ProtocolModel):
    """The frozen coordinates of one Climb release. Spec section 6.6.

    Every field is required and concrete. There is no field that describes the
    wheel, the plugin, or the commit this document was authored at: those are
    facts about artifacts that do not exist yet when the release is written,
    and decision 0026 puts them where they can be known — stamped into the
    wheel, and witnessed by the website's bootstrap document.

    ``starter_skill_digest`` and ``starter_skill_object_url`` are two halves of
    one coordinate and neither substitutes for the other. The digest says
    *which* Skill the release measured — spec section 4.1 and decisions 0008
    make it the ordered content-tree digest, not a file hash — and the URL says
    where a machine that does not already hold those bytes can obtain them, and
    which bytes the address itself promises.
    """

    schema_version: Literal["techtree.release-core.v1"]
    release_id: ReleaseId
    cli_version: Version
    protocol_version: NonEmptyString
    engine_digest: ConcreteDigest
    catalog_digest: ConcreteDigest
    intro_climb_reference: NonEmptyString
    starter_skill_digest: ConcreteDigest
    starter_skill_object_url: ObjectUrl
    skill_improver_digest: ConcreteDigest
    minimum_host_hermes_version: Version
    maximum_tested_host_hermes_version: Version
    subject_hermes_version: Version
    publication: PublicationCoordinates


class ReleaseInputs(ProtocolModel):
    """The founder-owned half of a ReleaseCore. Spec section 4.5.

    Every value here is a decision a person makes and freezes — the published
    version, the release identifier, the Skill artifacts, the host Hermes
    range. None of them can be derived from this repository, so they are held
    in one hand-edited file that the generator reads, rather than passed as
    command options that would leave the generated document unreproducible.

    The remaining ReleaseCore coordinates are absent on purpose. A release
    input file that tried to state the engine digest or the protocol version
    would be asserting something the source tree already answers.
    """

    schema_version: Literal["techtree.release-inputs.v1"]
    release_id: ReleaseId
    cli_version: Version
    intro_climb_reference: NonEmptyString
    starter_skill_digest: ConcreteDigest
    starter_skill_object_url: ObjectUrl
    skill_improver_digest: ConcreteDigest
    minimum_host_hermes_version: Version
    maximum_tested_host_hermes_version: Version
    publication: PublicationCoordinates
