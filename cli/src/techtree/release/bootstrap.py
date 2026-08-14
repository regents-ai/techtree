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
repeat six coordinates — the CLI version, the CLI source commit, the minimum
host Hermes version, the introductory Climb, and the starter Skill's digest and
object URL. Repeated values drift, and when they do the website tells operators
to install one thing while the CLI believes another. Each repeat is compared
individually here so a failure names the coordinate.

The starter Skill is the newest of those repeats and the one with the most to
lose. Spec sections 4.1 and 10.5 make the wrapper the thing that says where the
public Skill object is served from, and the release document the thing that
says which bytes count. A wrapper that pointed at a different object, or named
a different digest, would send an operator to fetch a Skill this release never
measured — so both halves are compared, and a placeholder release is expected
to repeat the placeholder rather than quietly fill it in.

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
from techtree.release.models import COMMIT_PATTERN, OBJECT_URL_PATTERN, ReleaseCore

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

_COMMIT_RE = re.compile(COMMIT_PATTERN)
_OBJECT_URL_RE = re.compile(OBJECT_URL_PATTERN)
_DIGEST_RE = re.compile(DIGEST_PATTERN)

#: Every field the website importer requires, and the kind it requires. Listed
#: as paths so a failure can name the field the way the document spells it.
_REQUIRED_FIELDS: Final[tuple[tuple[tuple[str, ...], str], ...]] = (
    (("channel",), "string"),
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
    (("starter_skill", "object_url"), "object URL"),
    (("starter_skill", "digest"), "digest"),
)

#: The kinds whose name does not take "a". Spelled out rather than derived,
#: because the list is short and a vowel rule would be wrong for "URL".
_IRREGULAR_ARTICLES: Final[Mapping[str, str]] = {
    "argv": "an argument array",
    "object URL": "an object URL",
}


def verify_bootstrap_document(core: ReleaseCore, raw: bytes) -> ReleaseVerification:
    """Check one bootstrap document against the ReleaseCore it should wrap."""
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
            _placeholder_declaration_check(core, document),
            _coordinate_check(
                "bootstrap_cli_version",
                document,
                ("cli", "version"),
                core.cli_version,
                "the CLI version",
            ),
            _coordinate_check(
                "bootstrap_cli_source_revision",
                document,
                ("cli", "source_revision"),
                core.cli_source_commit,
                "the CLI source commit",
            ),
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
                "bootstrap_starter_skill_digest",
                document,
                ("starter_skill", "digest"),
                core.starter_skill_digest,
                "the starter Skill digest",
            ),
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


def _placeholder_declaration_check(
    core: ReleaseCore, document: dict[str, JsonValue]
) -> ReleaseCheck:
    declared = _lookup(document, ("placeholder_release",))
    if declared == core.placeholder_release:
        state = "a placeholder" if core.placeholder_release else "a real"
        return _passed(
            "bootstrap_placeholder_declaration",
            f"both documents declare {state} release.",
        )
    return _failed(
        "bootstrap_placeholder_declaration",
        BOOTSTRAP_RELEASE_MISMATCH,
        f"the bootstrap document declares placeholder_release={declared} and "
        f"the ReleaseCore declares {core.placeholder_release}; one of them is "
        "telling operators the wrong thing about this release.",
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
    """The published install command must install the published version."""
    argv = _string_list(_lookup(document, ("cli", "install_argv")))
    distribution = _lookup(document, ("cli", "distribution"))
    pin = f"{distribution}=={core.cli_version}"
    if pin in argv:
        return _passed(
            "bootstrap_cli_install_argv",
            f"the published install command pins {pin}.",
        )
    return _failed(
        "bootstrap_cli_install_argv",
        BOOTSTRAP_RELEASE_MISMATCH,
        f"the published install command does not pin {pin}; it is {argv}.",
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
