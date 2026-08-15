"""Obtaining the release's starter Skill. Spec section 10.5, decisions 0008.

Three questions, and the second is the one that matters.

*Does the right Skill arrive?* A local copy is read, scanned, and cached under
the Techtree home, and a second call reuses what is already there.

*Is anything else refused?* Bytes that are not what the address promised,
bytes that do not hash to the pinned tree digest, a Skill the ordinary policy
would reject from anybody, a cached directory that has been edited, and a
source that is not a source. Every one of those leaves the home unchanged.

*Is it the tree digest?* Decisions document 0008 pins the starter Skill by its
``SkillArtifact.root_digest`` — the ordered content-tree digest the scanner
computes — and not by the hash of a file. The expected digest below is built
from the fixture's own bytes with the same construction the manifest builder
uses, so a change to either definition shows up here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fixtures.starter import (
    SKILL_FIXTURES,
    STARTER_FIXTURE,
    content_address,
    tree_digest,
)
from fixtures.starter import (
    release_pinning as release,
)
from techtree.canonical import sha256_digest_bytes
from techtree.errors import (
    NotFoundError,
    PrerequisiteError,
    UsageError,
    ValidationError,
    VerificationError,
)
from techtree.models.base import Digest
from techtree.paths import paths_from_root
from techtree.skills.starter import (
    STARTER_SKILL_DIGEST_MISMATCH,
    STARTER_SKILL_SOURCE_REFUSED,
    StarterSkillService,
)

#: Any digest that is not the fixture's, spelled so a failure is readable.
OTHER_DIGEST: Digest = f"sha256:{'1' * 64}"

#: The bytes the published object serves, and the address it serves them at.
STARTER_BYTES = (STARTER_FIXTURE / "SKILL.md").read_bytes()
PUBLISHED_URL = content_address(sha256_digest_bytes(STARTER_BYTES))


@pytest.fixture
def pinned() -> Digest:
    return tree_digest(STARTER_FIXTURE)


@pytest.fixture
def service(temp_techtree_home: Path) -> StarterSkillService:
    return StarterSkillService(paths_from_root(temp_techtree_home))


# ---------------------------------------------------------------------------
# The Skill arrives
# ---------------------------------------------------------------------------


def test_a_local_copy_is_verified_and_cached_under_the_techtree_home(
    temp_techtree_home: Path, service: StarterSkillService, pinned: Digest
) -> None:
    """The cache is Techtree's own directory, named by the verified digest."""
    materialized = service.materialize(
        release=release(pinned), local_file=STARTER_FIXTURE
    )

    paths = paths_from_root(temp_techtree_home)
    assert materialized.origin == "local_file"
    assert materialized.root == paths.skill_cache_dir(pinned)
    assert materialized.root.is_relative_to(paths.cache_dir)
    assert materialized.root_digest == pinned
    assert materialized.entrypoint.read_text("utf-8") == (
        (STARTER_FIXTURE / "SKILL.md").read_text("utf-8")
    )
    assert materialized.file_count == 1


def test_naming_the_entry_file_and_naming_its_directory_agree(
    service: StarterSkillService, pinned: Digest
) -> None:
    """``--from-file`` accepts a Skill the way every other command does."""
    from_directory = service.materialize(
        release=release(pinned), local_file=STARTER_FIXTURE
    )
    from_entrypoint = service.materialize(
        release=release(pinned), local_file=STARTER_FIXTURE / "SKILL.md"
    )

    assert from_directory.root_digest == from_entrypoint.root_digest == pinned


def test_a_published_release_needs_nobody_to_name_a_source(
    temp_techtree_home: Path, pinned: Digest
) -> None:
    """Spec section 10.5: the release carries the address, so the caller need not.

    The fetcher is substituted rather than a socket opened — what is under test
    is which address the service decides to read, and that decision is made
    before any transport is involved.
    """
    asked: list[str] = []

    def download(url: str) -> bytes:
        asked.append(url)
        return STARTER_BYTES

    service = StarterSkillService(
        paths_from_root(temp_techtree_home), download=download
    )
    materialized = service.materialize(
        release=release(pinned, object_url=PUBLISHED_URL)
    )

    assert asked == [PUBLISHED_URL]
    assert materialized.origin == "release"
    assert materialized.root_digest == pinned


def test_the_published_address_buys_the_bytes_it_serves_no_trust(
    temp_techtree_home: Path, pinned: Digest
) -> None:
    """The address promises which bytes it returns, and they are checked first."""
    service = StarterSkillService(
        paths_from_root(temp_techtree_home),
        download=lambda url: b"---\nname: other\n---\n\nSomething else.\n",
    )

    with pytest.raises(VerificationError) as raised:
        service.materialize(release=release(pinned, object_url=PUBLISHED_URL))

    assert raised.value.code == STARTER_SKILL_DIGEST_MISMATCH
    assert raised.value.details["url"] == PUBLISHED_URL


def test_a_mirror_that_promises_nothing_is_still_held_to_the_tree_digest(
    temp_techtree_home: Path, pinned: Digest
) -> None:
    """An address with no digest in it is checked by the release's digest."""
    mirror = "https://mirror.example.com/starter/SKILL.md"
    service = StarterSkillService(
        paths_from_root(temp_techtree_home),
        download=lambda url: b"---\nname: other\n---\n\nSomething else.\n",
    )

    with pytest.raises(VerificationError) as raised:
        service.materialize(release=release(pinned), url=mirror)

    assert raised.value.code == STARTER_SKILL_DIGEST_MISMATCH
    assert raised.value.details["source"] == mirror


def test_a_cache_hit_never_reaches_for_the_published_address(
    temp_techtree_home: Path, pinned: Digest
) -> None:
    """What is already proved on this machine is not re-fetched."""

    def refuse(url: str) -> bytes:
        raise AssertionError(f"nothing should be fetched, but {url} was")

    service = StarterSkillService(paths_from_root(temp_techtree_home), download=refuse)
    published = release(pinned, object_url=PUBLISHED_URL)
    service.materialize(release=published, local_file=STARTER_FIXTURE)

    assert service.materialize(release=published).origin == "cache"


def test_a_second_call_reuses_what_this_machine_already_has(
    service: StarterSkillService, pinned: Digest
) -> None:
    """A cache exists so the second guided run does not fetch anything."""
    first = service.materialize(release=release(pinned), local_file=STARTER_FIXTURE)
    second = service.materialize(release=release(pinned))

    assert first.origin == "local_file"
    assert second.origin == "cache"
    assert second.root == first.root
    assert second.root_digest == pinned


def test_a_cached_skill_is_re_verified_rather_than_trusted(
    temp_techtree_home: Path, pinned: Digest
) -> None:
    """A cached directory somebody edited is not a shortcut past the check."""
    published = release(pinned, object_url=PUBLISHED_URL)
    service = StarterSkillService(
        paths_from_root(temp_techtree_home), download=lambda url: STARTER_BYTES
    )
    cached = service.materialize(release=published, local_file=STARTER_FIXTURE).root
    entrypoint = cached / "SKILL.md"
    entrypoint.chmod(0o600)
    entrypoint.write_text("something else entirely\n", encoding="utf-8")

    # The edited copy is not reused: the Skill is obtained again and verified.
    repaired = service.materialize(release=published)
    assert repaired.origin == "release"
    assert repaired.root_digest == pinned
    assert (repaired.root / "SKILL.md").read_bytes() == STARTER_BYTES


# ---------------------------------------------------------------------------
# What is refused
# ---------------------------------------------------------------------------


def test_bytes_that_are_not_the_pinned_skill_are_refused(
    temp_techtree_home: Path, service: StarterSkillService
) -> None:
    """The release names the Skill; a caller only names where to look."""
    with pytest.raises(VerificationError) as raised:
        service.materialize(release=release(OTHER_DIGEST), local_file=STARTER_FIXTURE)

    assert raised.value.code == STARTER_SKILL_DIGEST_MISMATCH
    assert raised.value.details["expected"] == OTHER_DIGEST
    # Nothing was published, and no staging residue was left behind.
    paths = paths_from_root(temp_techtree_home)
    assert not paths.skill_cache_dir(OTHER_DIGEST).exists()
    assert (
        sorted(
            item.name for item in paths.skills_cache_dir().iterdir() if item.is_dir()
        )
        == []
    )


def test_a_skill_the_ordinary_policy_refuses_is_refused_here_too(
    temp_techtree_home: Path, service: StarterSkillService
) -> None:
    """There is no privileged path for a Skill because a release named it."""
    secret_skill = SKILL_FIXTURES / "invalid-secret"

    with pytest.raises(ValidationError) as raised:
        service.materialize(
            release=release(tree_digest(secret_skill)), local_file=secret_skill
        )

    assert raised.value.code == STARTER_SKILL_SOURCE_REFUSED
    paths = paths_from_root(temp_techtree_home)
    assert not any(paths.skills_cache_dir().glob("sha256-*"))


def test_a_source_that_is_not_there_is_refused(
    service: StarterSkillService, pinned: Digest, tmp_path: Path
) -> None:
    with pytest.raises(NotFoundError) as raised:
        service.materialize(
            release=release(pinned), local_file=tmp_path / "nowhere" / "SKILL.md"
        )

    assert raised.value.code == STARTER_SKILL_SOURCE_REFUSED


def test_naming_two_sources_is_refused(
    service: StarterSkillService, pinned: Digest
) -> None:
    with pytest.raises(UsageError) as raised:
        service.materialize(
            release=release(pinned),
            local_file=STARTER_FIXTURE,
            url="https://example.invalid/SKILL.md",
        )

    assert raised.value.code == STARTER_SKILL_SOURCE_REFUSED


def test_a_published_address_that_cannot_be_reached_is_a_typed_refusal(
    temp_techtree_home: Path, pinned: Digest
) -> None:
    """Nothing is invented when the object cannot be obtained."""

    def offline(url: str) -> bytes:
        raise PrerequisiteError(
            f"the starter Skill could not be fetched from {url}",
            code=STARTER_SKILL_SOURCE_REFUSED,
            retryable=True,
        )

    service = StarterSkillService(paths_from_root(temp_techtree_home), download=offline)

    with pytest.raises(PrerequisiteError) as raised:
        service.materialize(release=release(pinned, object_url=PUBLISHED_URL))

    assert raised.value.code == STARTER_SKILL_SOURCE_REFUSED


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com/SKILL.md",
        "http://example.com/SKILL.md",
        "not a url",
        "",
    ],
)
def test_a_source_that_is_not_a_web_address_is_never_opened(
    temp_techtree_home: Path, pinned: Digest, url: str
) -> None:
    """Nothing reaches the network layer until the URL is one Techtree fetches."""

    def never_called(_: str) -> bytes:
        raise AssertionError("the downloader must not be reached")

    service = StarterSkillService(
        paths_from_root(temp_techtree_home), download=never_called
    )

    with pytest.raises(UsageError) as raised:
        service.materialize(release=release(pinned), url=url)

    assert raised.value.code == STARTER_SKILL_SOURCE_REFUSED
