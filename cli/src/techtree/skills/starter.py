"""Obtaining the release's starter Skill. Spec section 10.5, decisions 0008.

The guided first run needs a Skill before it can prepare anything, and the
release names exactly which one: ``starter_skill_digest``. This module is how
those bytes reach a machine — read from a file a person names, or fetched from
a source a caller names — and how they are proved to be the right ones before
anything is done with them.

Four rules decide everything here.

*The release names the Skill; the caller only names where to look.* A source
is a hint about where bytes might be found. What makes them the starter Skill
is that they hash to the digest this build's ReleaseCore pins, and that check
is made against the release document, never against anything a caller passed
in. So a wrong URL, a stale download, or a helpful mirror serving something
else all end the same way: refused.

*A release that published its Skill needs nobody to name a source.* Spec
sections 4.1 and 10.5 make the starter Skill a public object at an exact URL,
and the release carries that URL as ``starter_skill_object_url``. So a caller
who names nothing gets the published object, and the identity check over what
arrives is the same one a hand-typed URL goes through — the release's address
buys the bytes no trust at all. A build whose URL is still the placeholder has
published nothing, and says that instead of guessing.

*The digest is the Skill's root digest, not a file hash.* Decisions document
0008 fixes this: the starter Skill is evaluated through the kernel, so it is
pinned by its ``SkillArtifact.root_digest`` — the ordered content-tree digest
the scanner computes. Materializing therefore *scans*, exactly as preparing a
participant's own Skill does, and compares the tree digest. A Skill that the
ordinary scanner or the ordinary policy refuses is refused here too. There is
no privileged path for a Skill because a release named it.

*A placeholder release has no starter Skill, and says so.* Decision R10 makes
``placeholder_release`` a permanent schema rule, and a build whose starter
digest is still the placeholder spelling has not chosen a Skill. Inventing one
would give an operator a demo that measured something nobody pinned, so the
refusal is typed and carries the next step.

*The cache is Techtree's own.* Materialized Skills live under the Techtree
home, in a directory named by the digest they were verified against — never in
package resources, which are the build's and are read-only. A cache entry is
re-scanned and re-verified before it is reused, so a cached directory that
somebody edited is not a shortcut past the check.

What this module does not do is prepare a draft. It returns a path, and that
path goes through ``climb prepare`` like any other: scanner, policy, draft,
confirmation. Decisions 0008 and spec section 10.5 both put the starter Skill
inside the ordinary path rather than beside it.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from ipaddress import ip_address
from pathlib import Path
from typing import Final, Literal
from urllib.parse import urlsplit

from filelock import FileLock, Timeout

from techtree.constants import MAX_SKILL_TOTAL_BYTES
from techtree.errors import (
    NotFoundError,
    PrerequisiteError,
    UsageError,
    ValidationError,
    VerificationError,
)
from techtree.fs import ensure_private_directory, remove_tree
from techtree.manifests.builder import skill_content_digest
from techtree.models.base import Digest
from techtree.models.cli import NextAction
from techtree.models.skill import SKILL_ENTRY_FILE, SkillFile
from techtree.paths import TechtreePaths
from techtree.release.models import (
    PLACEHOLDER_DIGEST,
    PLACEHOLDER_OBJECT_URL,
    ReleaseCore,
)
from techtree.skills.policy import default_instruction_skill_policy
from techtree.skills.scanner import SkillScanResult, resolve_skill_root, scan_skill

__all__ = [
    "STARTER_SKILL_DIGEST_MISMATCH",
    "STARTER_SKILL_NOT_PINNED",
    "STARTER_SKILL_SOURCE_REFUSED",
    "STARTER_SKILL_UNAVAILABLE",
    "Downloader",
    "MaterializedStarterSkill",
    "StarterSkillService",
]

#: This build pins no starter Skill yet. Decision R10: a placeholder release
#: has not chosen one, and saying so is the honest answer.
STARTER_SKILL_NOT_PINNED: Final = "starter_skill_not_pinned"

#: Nothing here holds the pinned Skill and nowhere was named to get it from.
STARTER_SKILL_UNAVAILABLE: Final = "starter_skill_unavailable"

#: A source that will not be read at all — an unusable URL, an unreachable
#: one, or a file that is not there.
STARTER_SKILL_SOURCE_REFUSED: Final = "starter_skill_source_refused"

#: Bytes arrived and are not the Skill this release pins.
STARTER_SKILL_DIGEST_MISMATCH: Final = "starter_skill_digest_mismatch"

#: One materialization at a time per Techtree home, for the same reason an
#: engine install takes a lock: two of them would be writing one directory.
_CACHE_LOCK_FILENAME: Final = ".skills.lock"
_CACHE_LOCK_TIMEOUT_SECONDS: Final = 120.0

#: Where a download is staged before it has been proved. Named so that a
#: leftover from an interrupted materialization is recognizable.
_STAGING_PREFIX: Final = ".materializing-"

#: How long a fetch may take before it is a hang rather than a slow network.
DOWNLOAD_TIMEOUT_SECONDS: Final = 60.0

type Downloader = Callable[[str], bytes]
"""Returns the bytes one URL serves, or raises a typed refusal."""


@dataclass(frozen=True)
class MaterializedStarterSkill:
    """Where the pinned starter Skill is, and what proved it is that Skill."""

    root: Path
    entrypoint: Path
    root_digest: Digest
    file_count: int
    total_bytes: int
    origin: Literal["cache", "local_file", "download", "release"]


class StarterSkillService:
    """Materializes the release's starter Skill into the Techtree home."""

    def __init__(
        self,
        paths: TechtreePaths,
        *,
        download: Downloader | None = None,
    ) -> None:
        self._paths = paths
        self._download = download or _download_document

    def materialize(
        self,
        *,
        release: ReleaseCore,
        local_file: Path | None = None,
        url: str | None = None,
    ) -> MaterializedStarterSkill:
        """Return the pinned starter Skill, obtaining it if this home lacks it."""
        pinned = _pinned_digest(release)
        if local_file is not None and url is not None:
            raise UsageError(
                "name one source for the starter Skill, not two",
                code=STARTER_SKILL_SOURCE_REFUSED,
            )

        ensure_private_directory(self._paths.cache_dir)
        ensure_private_directory(self._paths.skills_cache_dir())
        destination = self._paths.skill_cache_dir(pinned)

        with self._cache_lock():
            origin: Literal["local_file", "download", "release"]
            if local_file is not None:
                origin, source = "local_file", str(local_file)
            elif url is not None:
                origin, source = "download", url
            else:
                cached = _verified_cache_entry(destination, pinned)
                if cached is not None:
                    return _describe(cached, origin="cache")
                origin, source = "release", _published_source(release, destination)

            staging = destination.parent / f"{_STAGING_PREFIX}{destination.name}"
            remove_tree(staging)
            try:
                if local_file is not None:
                    _stage_local(local_file, staging)
                else:
                    _require_fetchable(source)
                    _stage_document(self._download(source), staging)
                _verify_scan(staging, pinned, source=source)
                remove_tree(destination)
                staging.replace(destination)
            except BaseException:
                remove_tree(staging)
                raise

            # Re-scanned where it now lives, so what is described is what a
            # caller will hand to ``climb prepare`` and not what was staged.
            published = _verified_cache_entry(destination, pinned)

        if published is None:  # pragma: no cover - defended, never expected
            raise VerificationError(
                "the starter Skill did not survive being written to the cache",
                code=STARTER_SKILL_DIGEST_MISMATCH,
                details={"expected": pinned, "cache": str(destination)},
            )
        return _describe(published, origin=origin)

    @contextmanager
    def _cache_lock(self) -> Iterator[None]:
        """Serialize materialization within one Techtree home."""
        lock = FileLock(
            str(self._paths.skills_cache_dir() / _CACHE_LOCK_FILENAME),
            timeout=_CACHE_LOCK_TIMEOUT_SECONDS,
        )
        try:
            lock.acquire()
        except Timeout as error:
            raise PrerequisiteError(
                "another Techtree process is materializing a Skill",
                code=STARTER_SKILL_UNAVAILABLE,
                details={"path": str(self._paths.skills_cache_dir())},
                retryable=True,
            ) from error
        try:
            yield
        finally:
            lock.release()


# ---------------------------------------------------------------------------
# The steps
# ---------------------------------------------------------------------------


def _pinned_digest(release: ReleaseCore) -> Digest:
    """Return the starter Skill this release chose, or refuse because it has not."""
    if release.starter_skill_digest == PLACEHOLDER_DIGEST:
        raise PrerequisiteError(
            "this build's release has not chosen a starter Skill yet, so there "
            "is no Skill to obtain. A release that has chosen one names its "
            "digest, and this one still carries the placeholder.",
            code=STARTER_SKILL_NOT_PINNED,
            details={
                "release_id": release.release_id,
                "placeholder_fields": ", ".join(release.placeholder_fields),
            },
            next_actions=[
                NextAction(
                    id="inspect_release",
                    label="See which release coordinates are still unchosen",
                    reason=(
                        "The starter Skill is one of this build's placeholder "
                        "coordinates. A build that pins one obtains it without "
                        "anybody naming a file."
                    ),
                    cli=["techtree", "release", "info"],
                    hermes_tool=None,
                    hermes_args=None,
                    requires_user_confirmation=False,
                )
            ],
        )
    return release.starter_skill_digest


def _published_source(release: ReleaseCore, cache: Path) -> str:
    """Return the address this release publishes its starter Skill at.

    Reached only when nothing is cached and nobody named a source, so the
    refusal here is the one a person sees when there is genuinely nowhere to
    look: this machine does not hold the Skill and this build's release never
    said where it lives.
    """
    if release.starter_skill_object_url == PLACEHOLDER_OBJECT_URL:
        raise NotFoundError(
            "this machine does not hold the starter Skill this release pins, "
            "and the release does not say where it is published yet, so there "
            "is nowhere to get it from",
            code=STARTER_SKILL_UNAVAILABLE,
            details={
                "expected": release.starter_skill_digest,
                "cache": str(cache),
                "release_id": release.release_id,
            },
            next_actions=[
                NextAction(
                    id="name_a_starter_skill_source",
                    # The release names the Skill, so a copy can still be
                    # proved against it. What is missing is only the address.
                    label="Name a local copy of the starter Skill",
                    reason=(
                        "This release pins which Skill counts, so a copy you "
                        "already have is checked against that digest and "
                        "refused unless it matches. Only the address it will "
                        "be published at is still unchosen."
                    ),
                    cli=["techtree", "skill", "starter", "--from-file", "PATH"],
                    hermes_tool=None,
                    hermes_args=None,
                    requires_user_confirmation=False,
                )
            ],
        )
    return release.starter_skill_object_url


def _stage_local(source: Path, staging: Path) -> None:
    """Copy a Skill a person named on this machine into the staging tree."""
    try:
        root = resolve_skill_root(source)
    except (NotFoundError, ValidationError) as error:
        raise NotFoundError(
            f"the starter Skill could not be read from {source}: {error.message}",
            code=STARTER_SKILL_SOURCE_REFUSED,
            details={"path": str(source)},
        ) from error

    # Scanned before it is copied, so nothing the policy refuses is ever
    # written into the Techtree home.
    scan = _scan(root, source=str(source))
    ensure_private_directory(staging)
    for item in scan.files:
        target = staging / item.relative_path
        ensure_private_directory(target.parent)
        target.write_bytes(item.source_path.read_bytes())
        target.chmod(0o600)


def _stage_document(data: bytes, staging: Path) -> None:
    """Write fetched bytes as the Skill's one entry file.

    A fetched starter Skill is a single ``SKILL.md`` document: that is what
    the v0.1 starter Skill is, and no release coordinate names an archive
    format a tree could arrive in. A multi-file starter Skill would need one,
    chosen in a decision rather than guessed at here.
    """
    ensure_private_directory(staging)
    entrypoint = staging / SKILL_ENTRY_FILE
    entrypoint.write_bytes(data)
    entrypoint.chmod(0o600)


def _verify_scan(root: Path, expected: Digest, *, source: str) -> None:
    """Scan a staged Skill and refuse it unless it is the one that was pinned."""
    computed = _root_digest(_scan(root, source=source))
    if computed != expected:
        raise VerificationError(
            "what was obtained is not the starter Skill this release pins",
            code=STARTER_SKILL_DIGEST_MISMATCH,
            details={"expected": expected, "computed": computed, "source": source},
        )


def _verified_cache_entry(root: Path, expected: Digest) -> SkillScanResult | None:
    """Return a cached Skill that still is what its directory name claims."""
    if not (root / SKILL_ENTRY_FILE).is_file():
        return None
    try:
        scan = scan_skill(root, default_instruction_skill_policy())
    except (NotFoundError, ValidationError):
        return None
    return scan if _root_digest(scan) == expected else None


def _scan(root: Path, *, source: str) -> SkillScanResult:
    """Run the ordinary scanner and policy over a Skill, and report refusals."""
    try:
        return scan_skill(root, default_instruction_skill_policy())
    except ValidationError as error:
        raise ValidationError(
            f"the starter Skill obtained from {source} is not a Skill Techtree "
            f"would accept from anyone: {error.message}",
            code=STARTER_SKILL_SOURCE_REFUSED,
            details={"source": source},
        ) from error


def _root_digest(scan: SkillScanResult) -> Digest:
    """Return the content-tree digest decisions 0008 pins a starter Skill by."""
    return skill_content_digest(
        [
            SkillFile(
                path=item.relative_path.as_posix(),
                media_type=item.media_type,
                size=item.size,
                digest=item.digest,
            )
            for item in scan.files
        ]
    )


def _describe(
    scan: SkillScanResult,
    *,
    origin: Literal["cache", "local_file", "download", "release"],
) -> MaterializedStarterSkill:
    """Say where the verified Skill is and how it got there."""
    return MaterializedStarterSkill(
        root=scan.root,
        entrypoint=scan.root / SKILL_ENTRY_FILE,
        root_digest=_root_digest(scan),
        file_count=len(scan.files),
        total_bytes=sum(item.size for item in scan.files),
        origin=origin,
    )


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------


def _download_document(url: str) -> bytes:
    """Fetch one document over HTTP, bounded.

    Transport is not what makes these bytes trustworthy — the release's digest
    is, and it is checked afterwards on whatever arrives. This is only the
    transport, and it is reached only after the service has decided the URL is
    one Techtree fetches from at all.
    """
    request = urllib.request.Request(
        url, method="GET", headers={"Accept": "text/markdown, text/plain, */*"}
    )
    try:
        with urllib.request.urlopen(
            request, timeout=DOWNLOAD_TIMEOUT_SECONDS
        ) as response:
            data: bytes = response.read(MAX_SKILL_TOTAL_BYTES + 1)
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise PrerequisiteError(
            f"the starter Skill could not be fetched from {url}: "
            f"{getattr(error, 'reason', None) or error}",
            code=STARTER_SKILL_SOURCE_REFUSED,
            details={"url": url},
            retryable=True,
        ) from error

    if len(data) > MAX_SKILL_TOTAL_BYTES:
        raise ValidationError(
            f"{url} served more than the {MAX_SKILL_TOTAL_BYTES} bytes a Skill "
            "may hold, so it is not the starter Skill",
            code=STARTER_SKILL_SOURCE_REFUSED,
            details={"url": url, "maximum_total_bytes": str(MAX_SKILL_TOTAL_BYTES)},
        )
    return data


def _require_fetchable(url: str) -> None:
    """Refuse a URL that is not an ordinary web address before anything opens it.

    An ``https`` URL, or a plain ``http`` one only when it addresses this
    machine, which is what a local fixture server is. Every other scheme is
    refused rather than handed to a fetcher, because ``file:`` and friends
    would turn a URL into a local read. The check is here rather than inside
    the fetcher so that it holds for every fetcher, including a substituted
    one.
    """
    parts = urlsplit(url)
    if parts.scheme == "https" and parts.hostname:
        return
    if parts.scheme == "http" and _is_loopback(parts.hostname):
        return
    raise UsageError(
        "a starter Skill is fetched over https, or over http from this "
        f"machine; {url!r} is neither",
        code=STARTER_SKILL_SOURCE_REFUSED,
        details={"url": url},
    )


def _is_loopback(hostname: str | None) -> bool:
    """Return whether a host names this machine and nothing else."""
    if hostname is None:
        return False
    if hostname == "localhost":
        return True
    try:
        return ip_address(hostname).is_loopback
    except ValueError:
        return False
