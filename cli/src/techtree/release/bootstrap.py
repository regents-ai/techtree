"""Checking a website bootstrap document from the side that produced it.

Spec sections 9.3.2, 9.4 and 9.7.

The website publishes a ``BootstrapRelease``: the wrapper that tells a new
operator which CLI version to install, which plugin commit to install, and
which Climb to start with. It is generated after this repository's ReleaseCore
exists, it is served as exact bytes, and the website refuses to import one that
does not hold together.

This module checks the same document from the producing end, and it does that
for two different reasons that are worth keeping apart.

*Does the wrapper still name this release?* The bootstrap and the ReleaseCore
repeat four coordinates — the CLI version, the minimum host Hermes version, the
introductory Climb, and the starter Skill. Repeated values drift, and when they
do the website tells operators to install one thing while the CLI believes
another. Each repeat is compared individually here so a failure names the
coordinate.

The wrapper also states one coordinate the release document deliberately does
not carry: which source commit the published wheel was built from. Decisions
0026 puts that fact where it can be known — stamped into the wheel by the build
— so the comparison here is against the wheel itself, not against a claim the
release repeats about itself.

The starter Skill is the coordinate with the most to lose. Spec sections 4.1
and 10.5 make the wrapper the thing that says where the public Skill object is
served from, and the release document the thing that says which bytes count.
The wrapper carries both halves of the object: ``file_digest``, the bytes the
address returns, and ``tree_digest``, the one-file Skill the CLI builds out of
them and verifies before it runs anything. The address must be keyed by the
file digest, because that is what the website serves it under, and the tree
digest must be the one this release measured.

*Would the website accept these bytes at all?* The shape rules are the
website's, not this repository's, and they stay the website's: it re-checks
every one of them at import. Restating them here is a pre-flight, so that a
release that cannot be published is caught while it is still being assembled
rather than at deploy time.

One thing is deliberately not checked: the plugin commit. A ReleaseCore does
not contain one (spec section 6.6) precisely so that the plugin can embed the
ReleaseCore without a cycle, so nothing here can have an opinion about which
commit the wrapper pins — only that it pins a full, immutable one.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import datetime
from typing import Final

from techtree.models.base import DIGEST_PATTERN, JsonValue
from techtree.release.checks import (
    ReleaseCheck,
    ReleaseVerification,
)
from techtree.release.models import (
    OBJECT_URL_PATTERN,
    ReleaseCore,
    object_url_digest,
)
from techtree.release.provenance import COMMIT_PATTERN, BuildProvenance

__all__ = [
    "BOOTSTRAP_RELEASE_INVALID",
    "BOOTSTRAP_RELEASE_MISMATCH",
    "BOOTSTRAP_SCHEMA_VERSION",
    "verify_bootstrap_document",
]

#: The schema version the website's importer accepts, and nothing else.
BOOTSTRAP_SCHEMA_VERSION: Final = "techtree.bootstrap.v1alpha1"

BOOTSTRAP_RELEASE_INVALID: Final = "bootstrap_release_invalid"
BOOTSTRAP_RELEASE_MISMATCH: Final = "bootstrap_release_mismatch"

#: How the published install command names an interpreter to the installer.
#: The value beside it is never written here — it is read from the document
#: being checked (decision 0031).
_INTERPRETER_FLAG: Final = "--python"

_COMMIT_RE = re.compile(COMMIT_PATTERN)
_OBJECT_URL_RE = re.compile(OBJECT_URL_PATTERN)
_DIGEST_RE = re.compile(DIGEST_PATTERN)

#: Every field the website importer requires, and the kind it requires. Listed
#: as paths so a failure can name the field the way the document spells it.
_REQUIRED_FIELDS: Final[tuple[tuple[tuple[str, ...], str], ...]] = (
    (("channel",), "string"),
    # The website's own declaration of whether it is serving a development
    # bootstrap or a published one (decisions 0026 section 3). It says nothing
    # about the release document, which is concrete either way.
    (("placeholder_release",), "boolean"),
    (("published_at",), "timestamp"),
    (("minimums", "hermes_version"), "string"),
    (("cli", "distribution"), "string"),
    (("cli", "version"), "string"),
    (("cli", "install_argv"), "argv"),
    (("cli", "source_revision"), "commit"),
    (("hermes_plugin", "plugin_id"), "string"),
    (("hermes_plugin", "revision"), "commit"),
    (("hermes_plugin", "install_argv"), "argv"),
    (("hermes_plugin", "doctor_argv"), "argv"),
    (("introductory_climb", "reference"), "string"),
    (("introductory_climb", "host_prompt"), "string"),
    (("starter_skill", "name"), "string"),
    (("starter_skill", "object_url"), "object URL"),
    (("starter_skill", "file_digest"), "digest"),
    (("starter_skill", "tree_digest"), "digest"),
    (("starter_skill", "media_type"), "string"),
    (("starter_skill", "size"), "byte count"),
)

#: The kinds whose name does not take "a". Spelled out rather than derived,
#: because the list is short and a vowel rule would be wrong for "URL".
_IRREGULAR_ARTICLES: Final[Mapping[str, str]] = {
    "argv": "an argument array",
    "object URL": "an object URL",
    "byte count": "a positive byte count",
}


def verify_bootstrap_document(
    core: ReleaseCore, raw: bytes, *, wheel: BuildProvenance, wheel_sha256: str
) -> ReleaseVerification:
    """Check one bootstrap document against the release it should wrap.

    ``wheel`` is the provenance stamped into the CLI wheel this bootstrap
    publishes. It is required rather than optional: the document names a source
    commit, and the only thing that can confirm it is the artifact itself.

    ``wheel_sha256`` is that same file's SHA-256, in lowercase hex without a
    prefix, computed by the caller from the bytes it holds. The stamp cannot
    carry it — decision 0026: an artifact never names its own identity — so the
    one thing that can confirm the digest the document publishes is a fresh
    hash of the file. Without this the gate would bind a wheel by name and by
    commit while never checking the number a participant actually installs
    against.
    """
    try:
        document = json.loads(raw)
    except ValueError as error:
        return _one(
            _failed(
                "bootstrap_document",
                BOOTSTRAP_RELEASE_INVALID,
                f"the bootstrap document is not JSON: {error}",
            )
        )
    if not isinstance(document, dict):
        return _one(
            _failed(
                "bootstrap_document",
                BOOTSTRAP_RELEASE_INVALID,
                "the bootstrap document must be a JSON object.",
            )
        )

    schema = _schema_version_check(document)
    if schema.status == "failed":
        return _one(schema)

    contract = _importer_contract_check(document)
    checks = [schema, contract]
    if contract.status == "failed":
        # Every comparison below reads a field the contract just found missing
        # or mis-typed, so running them would only repeat one failure.
        return ReleaseVerification(verified=False, checks=checks)

    checks.extend(
        [
            _coordinate_check(
                "bootstrap_cli_version",
                document,
                ("cli", "version"),
                core.cli_version,
                "the CLI version",
            ),
            _wheel_commit_check(document, wheel),
            _wheel_digest_check(document, wheel_sha256),
            _coordinate_check(
                "bootstrap_hermes_minimum",
                document,
                ("minimums", "hermes_version"),
                core.minimum_host_hermes_version,
                "the minimum host Hermes version",
            ),
            _coordinate_check(
                "bootstrap_intro_climb",
                document,
                ("introductory_climb", "reference"),
                core.intro_climb_reference,
                "the introductory Climb",
            ),
            _coordinate_check(
                "bootstrap_starter_skill_object_url",
                document,
                ("starter_skill", "object_url"),
                core.starter_skill_object_url,
                "the starter Skill object URL",
            ),
            _coordinate_check(
                "bootstrap_starter_skill_tree_digest",
                document,
                ("starter_skill", "tree_digest"),
                core.starter_skill_digest,
                "the starter Skill tree digest",
            ),
            _starter_skill_address_check(document),
            _cli_install_argv_check(core, document),
            _plugin_install_argv_check(document),
        ]
    )
    return ReleaseVerification(
        verified=not any(check.status == "failed" for check in checks),
        checks=checks,
    )


# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------


def _schema_version_check(document: dict[str, JsonValue]) -> ReleaseCheck:
    found = document.get("schema_version")
    if found == BOOTSTRAP_SCHEMA_VERSION:
        return _passed(
            "bootstrap_schema_version",
            f"the bootstrap document is a {BOOTSTRAP_SCHEMA_VERSION}.",
        )
    return _failed(
        "bootstrap_schema_version",
        BOOTSTRAP_RELEASE_INVALID,
        f"the bootstrap document declares {found!r}; the website imports only "
        f"{BOOTSTRAP_SCHEMA_VERSION}.",
    )


def _importer_contract_check(document: dict[str, JsonValue]) -> ReleaseCheck:
    """Report every field the website would refuse the document over."""
    problems = [
        f"{'.'.join(path)} must be {_article(kind)}"
        for path, kind in _REQUIRED_FIELDS
        if not _holds(_lookup(document, path), kind)
    ]
    if problems:
        return _failed(
            "bootstrap_importer_contract",
            BOOTSTRAP_RELEASE_INVALID,
            "the website would refuse this document: " + "; ".join(problems) + ".",
        )
    return _passed(
        "bootstrap_importer_contract",
        f"all {len(_REQUIRED_FIELDS)} fields the website requires are present "
        "and well formed.",
    )


def _wheel_commit_check(
    document: dict[str, JsonValue], wheel: BuildProvenance
) -> ReleaseCheck:
    """The commit the wrapper publishes must be the wheel's own stamp.

    The release document says nothing about which commit built which artifact
    (decisions 0026), so this is the one coordinate here that is compared
    against the artifact rather than against the release: the wheel was
    stamped while it was built, and the wrapper repeats that stamp to
    operators.
    """
    published = _lookup(document, ("cli", "source_revision"))
    if published == wheel.source_commit:
        return _passed(
            "bootstrap_cli_source_revision",
            f"the published CLI was built from {wheel.source_commit}, which is "
            "what the wheel is stamped with.",
        )
    return _failed(
        "bootstrap_cli_source_revision",
        BOOTSTRAP_RELEASE_MISMATCH,
        f"the bootstrap document says the published CLI was built from "
        f"{published!r}, and the wheel is stamped {wheel.source_commit!r}.",
    )


def _wheel_digest_check(
    document: dict[str, JsonValue], wheel_sha256: str
) -> ReleaseCheck:
    """The digest the document publishes must be this wheel's own."""
    published = _lookup(document, ("cli", "wheel_sha256"))
    expected = f"sha256:{wheel_sha256}"
    if published == expected:
        return _passed(
            "bootstrap_cli_wheel_sha256",
            f"the published CLI wheel hashes to {expected}, which is what the "
            "bootstrap document names.",
        )
    return _failed(
        "bootstrap_cli_wheel_sha256",
        BOOTSTRAP_RELEASE_MISMATCH,
        f"the bootstrap document publishes the wheel digest {published!r}, and "
        f"the wheel handed to this check hashes to {expected!r}.",
    )


def _starter_skill_address_check(document: dict[str, JsonValue]) -> ReleaseCheck:
    """The published address must be keyed by the bytes it returns.

    The website files public objects under the digest of the file it serves,
    and refuses an address keyed by anything else. A fetcher checks what
    arrives against the address before it has built anything, so an address
    keyed by the tree digest — or by nothing at all — would leave the first
    check with nothing to compare against.
    """
    url = _lookup(document, ("starter_skill", "object_url"))
    file_digest = _lookup(document, ("starter_skill", "file_digest"))
    if not isinstance(url, str) or not isinstance(file_digest, str):
        raise AssertionError("both fields are validated before they are read")

    keyed = object_url_digest(url)
    if keyed == file_digest:
        return _passed(
            "bootstrap_starter_skill_address",
            f"the starter Skill is published at the digest of its own bytes, "
            f"{file_digest}.",
        )
    return _failed(
        "bootstrap_starter_skill_address",
        BOOTSTRAP_RELEASE_MISMATCH,
        f"the starter Skill address is keyed by {keyed} and the document says "
        f"the bytes it returns are {file_digest}; a fetcher would check what "
        "arrives against the wrong digest.",
    )


def _coordinate_check(
    identifier: str,
    document: dict[str, JsonValue],
    path: tuple[str, ...],
    expected: str,
    subject: str,
) -> ReleaseCheck:
    found = _lookup(document, path)
    if found == expected:
        return _passed(identifier, f"{subject} agrees: {expected}.")
    return _failed(
        identifier,
        BOOTSTRAP_RELEASE_MISMATCH,
        f"{subject} is {found!r} in the bootstrap document and {expected!r} in "
        "the ReleaseCore.",
    )


def _cli_install_argv_check(
    core: ReleaseCore, document: dict[str, JsonValue]
) -> ReleaseCheck:
    """The published install command must install the published version, and
    install it on the interpreter this same document requires.

    Left to choose, the installer takes whatever Python the machine already
    treats as its default — which can be a version Techtree does not support.
    The install then succeeds and the first thing the operator sees is Doctor
    saying the interpreter is wrong, after running the exact command this
    project published (decision 0031). So the command pins the interpreter.

    Which interpreter is not restated here. It is read from the document's own
    requirements, because a second written-out copy of one number is how a
    document ends up telling someone to install on an interpreter it also
    calls unsupported. That makes the two halves one fact, and this check is
    what keeps them one fact.
    """
    argv = _string_list(_lookup(document, ("cli", "install_argv")))
    distribution = _lookup(document, ("cli", "distribution"))
    interpreter = _lookup(document, ("minimums", "python"))
    pin = f"{distribution}=={core.cli_version}"

    if pin not in argv:
        return _failed(
            "bootstrap_cli_install_argv",
            BOOTSTRAP_RELEASE_MISMATCH,
            f"the published install command does not pin {pin}; it is {argv}.",
        )
    if not _pins_interpreter(argv, interpreter):
        return _failed(
            "bootstrap_cli_install_argv",
            BOOTSTRAP_RELEASE_MISMATCH,
            "the published install command does not pin the interpreter this "
            f"document requires: minimums.python is {interpreter!r} and the "
            f"command is {argv}.",
        )
    return _passed(
        "bootstrap_cli_install_argv",
        f"the published install command pins {pin} and installs it on the "
        f"Python {interpreter} this document requires.",
    )


def _pins_interpreter(argv: list[str], interpreter: JsonValue) -> bool:
    """Return whether the command names that interpreter to the installer."""
    if not isinstance(interpreter, str) or not interpreter.strip():
        return False
    wanted = (_INTERPRETER_FLAG, interpreter)
    return any(
        tuple(argv[position : position + 2]) == wanted
        for position in range(len(argv) - 1)
    )


def _plugin_install_argv_check(document: dict[str, JsonValue]) -> ReleaseCheck:
    """The published plugin command must install the commit it names."""
    revision = _lookup(document, ("hermes_plugin", "revision"))
    argv = _string_list(_lookup(document, ("hermes_plugin", "install_argv")))
    if revision in argv:
        return _passed(
            "bootstrap_plugin_install_argv",
            f"the published plugin command installs the exact commit {revision}.",
        )
    return _failed(
        "bootstrap_plugin_install_argv",
        BOOTSTRAP_RELEASE_MISMATCH,
        f"the published plugin command does not name the commit {revision} "
        f"the document pins; it is {argv}.",
    )


# ---------------------------------------------------------------------------
# Reading the document
# ---------------------------------------------------------------------------


def _lookup(document: dict[str, JsonValue], path: tuple[str, ...]) -> JsonValue:
    """Return the value at a path, or None when any step is absent."""
    current: JsonValue = document
    for step in path:
        if not isinstance(current, dict) or step not in current:
            return None
        current = current[step]
    return current


def _holds(value: JsonValue, kind: str) -> bool:
    """Return whether a value is of the kind the website requires."""
    match kind:
        case "string":
            return isinstance(value, str) and bool(value.strip())
        case "boolean":
            return isinstance(value, bool)
        case "timestamp":
            return isinstance(value, str) and _is_instant(value)
        case "commit":
            return isinstance(value, str) and _COMMIT_RE.fullmatch(value) is not None
        case "digest":
            return isinstance(value, str) and _DIGEST_RE.fullmatch(value) is not None
        case "object URL":
            return (
                isinstance(value, str) and _OBJECT_URL_RE.fullmatch(value) is not None
            )
        case "argv":
            return _is_argv(value)
        case "byte count":
            return isinstance(value, int) and not isinstance(value, bool) and value > 0
    raise AssertionError(f"unknown field kind {kind!r}")


def _is_instant(value: str) -> bool:
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return False
    return True


def _is_argv(value: JsonValue) -> bool:
    """Return whether a value is an argument array rather than a command line.

    A string here would be a shell command, and the whole point of publishing
    argument arrays is that nothing the website serves is ever handed to a
    shell (spec section 9.12).
    """
    if not isinstance(value, list) or not value:
        return False
    return all(isinstance(item, str) and bool(item.strip()) for item in value)


def _string_list(value: JsonValue) -> list[str]:
    """Return an already-validated argument array as strings."""
    if not isinstance(value, list):
        raise AssertionError("argument arrays are validated before they are read")
    return [item for item in value if isinstance(item, str)]


def _article(kind: str) -> str:
    return _IRREGULAR_ARTICLES.get(kind, f"a {kind}")


def _passed(identifier: str, detail: str) -> ReleaseCheck:
    return ReleaseCheck(id=identifier, status="passed", code="ok", detail=detail)


def _failed(identifier: str, code: str, detail: str) -> ReleaseCheck:
    return ReleaseCheck(id=identifier, status="failed", code=code, detail=detail)


def _one(check: ReleaseCheck) -> ReleaseVerification:
    return ReleaseVerification(verified=check.status != "failed", checks=[check])
