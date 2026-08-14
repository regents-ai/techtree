"""Fetching the starter Skill, over a real socket. Spec section 10.5.

The unit tests cover everything a local copy can prove. What they cannot
prove is that the fetch path is a fetch path: that a URL is opened, bytes come
back over a socket, and the same digest rule decides what happens next.

So this module stands up an HTTP server on the loopback interface and serves
four things from it — the real fixture Skill, a document that is not it, one
that is far too large, and a path that is not there. Nothing outside this
machine is ever contacted: the published starter Skill's real home is not a
test dependency, and a test that reached for it would fail on an aeroplane and
would be measuring somebody else's uptime.

The CLI's own answer on this build is here too, because this build pins no
starter Skill and the honest refusal is the behaviour an operator meets today.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from fixtures.runs.support import run_cli
from fixtures.starter import STARTER_FIXTURE, tree_digest
from fixtures.starter import release_pinning as release
from techtree.constants import MAX_SKILL_TOTAL_BYTES
from techtree.errors import (
    EXIT_NOT_FOUND,
    PrerequisiteError,
    ValidationError,
    VerificationError,
)
from techtree.models.base import Digest
from techtree.paths import paths_from_root
from techtree.skills.starter import (
    STARTER_SKILL_DIGEST_MISMATCH,
    STARTER_SKILL_SOURCE_REFUSED,
    STARTER_SKILL_UNAVAILABLE,
    StarterSkillService,
)

pytestmark = pytest.mark.integration

#: The founder's own starter Skill, which this release now pins by tree digest.
#: Distinct from ``STARTER_FIXTURE``: that one stands in for "a Skill", this one
#: is the artifact the packaged ReleaseCore names.
RELEASE_STARTER_SKILL = (
    Path(__file__).resolve().parents[2]
    / "release"
    / "skills"
    / "hello-world-starter-v1"
)
STARTER_SKILL_TREE_DIGEST = tree_digest(RELEASE_STARTER_SKILL)

STARTER_BYTES = (STARTER_FIXTURE / "SKILL.md").read_bytes()
WRONG_BYTES = b"# Not the starter Skill\n\nSomething else entirely.\n"
OVERSIZED_BYTES = b"#" + b"x" * MAX_SKILL_TOTAL_BYTES

_DOCUMENTS = {
    "/starter/SKILL.md": STARTER_BYTES,
    "/other/SKILL.md": WRONG_BYTES,
    "/huge/SKILL.md": OVERSIZED_BYTES,
}


class _Handler(BaseHTTPRequestHandler):
    """Serves three fixed documents and 404s everything else."""

    def do_GET(self) -> None:
        body = _DOCUMENTS.get(self.path)
        if body is None:
            self.send_error(404, "no such document")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/markdown")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        """Keep the test output about the test."""


@pytest.fixture(scope="module")
def origin() -> Iterator[str]:
    """Run the fixture server on the loopback interface for this module."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.socket.getsockname()[1]
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5.0)


@pytest.fixture
def pinned() -> Digest:
    return tree_digest(STARTER_FIXTURE)


def test_the_pinned_skill_is_fetched_verified_and_cached(
    tmp_path: Path, origin: str, pinned: Digest
) -> None:
    """A real socket, real bytes, and the same digest rule as everything else."""
    paths = paths_from_root(tmp_path / "home")
    service = StarterSkillService(paths)

    materialized = service.materialize(
        release=release(pinned), url=f"{origin}/starter/SKILL.md"
    )

    assert materialized.origin == "download"
    assert materialized.root_digest == pinned
    assert materialized.root == paths.skill_cache_dir(pinned)
    assert materialized.entrypoint.read_bytes() == STARTER_BYTES
    # And the second call needs no server at all.
    assert service.materialize(release=release(pinned)).origin == "cache"


def test_a_source_that_serves_something_else_is_refused(
    tmp_path: Path, origin: str, pinned: Digest
) -> None:
    """A mirror serving a different document does not become the starter Skill."""
    paths = paths_from_root(tmp_path / "home")
    service = StarterSkillService(paths)

    with pytest.raises(VerificationError) as raised:
        service.materialize(release=release(pinned), url=f"{origin}/other/SKILL.md")

    assert raised.value.code == STARTER_SKILL_DIGEST_MISMATCH
    assert not paths.skill_cache_dir(pinned).exists()


def test_a_source_that_serves_far_too_much_is_refused(
    tmp_path: Path, origin: str, pinned: Digest
) -> None:
    """A Skill has a size, and a document larger than one is not a Skill."""
    paths = paths_from_root(tmp_path / "home")

    with pytest.raises(ValidationError) as raised:
        StarterSkillService(paths).materialize(
            release=release(pinned), url=f"{origin}/huge/SKILL.md"
        )

    assert raised.value.code == STARTER_SKILL_SOURCE_REFUSED
    assert not paths.skill_cache_dir(pinned).exists()


def test_a_source_that_is_not_there_is_refused(
    tmp_path: Path, origin: str, pinned: Digest
) -> None:
    """An unreachable document is reported as one, and is worth retrying."""
    paths = paths_from_root(tmp_path / "home")

    with pytest.raises(PrerequisiteError) as raised:
        StarterSkillService(paths).materialize(
            release=release(pinned), url=f"{origin}/missing/SKILL.md"
        )

    assert raised.value.code == STARTER_SKILL_SOURCE_REFUSED
    assert raised.value.retryable is True


def test_the_cli_refuses_honestly_on_a_build_that_publishes_no_starter_skill(
    tmp_path: Path,
) -> None:
    """What an operator meets today, now that the Skill itself is pinned.

    This build names which Skill counts and has nowhere to fetch it from: the
    digest is bound and ``starter_skill_object_url`` is still the placeholder,
    because where the object will be served from is decided at deploy. So the
    refusal is about the address rather than about the Skill, and it offers the
    step that still works — naming a copy, which is checked against the pinned
    digest exactly as a download would be.
    """
    home = tmp_path / "home"
    home.mkdir()

    refused = run_cli(home, "skill", "starter")

    assert refused.exit_code == EXIT_NOT_FOUND
    envelope = refused.envelope()
    assert envelope["error"]["code"] == STARTER_SKILL_UNAVAILABLE
    assert envelope["error"]["details"]["expected"] == STARTER_SKILL_TREE_DIGEST
    assert [action["id"] for action in envelope["next_actions"]] == [
        "name_a_starter_skill_source"
    ]


def test_naming_a_local_copy_still_works_on_a_build_that_publishes_nothing(
    tmp_path: Path,
) -> None:
    """The next action the refusal offers has to be one that actually works."""
    home = tmp_path / "home"
    home.mkdir()

    obtained = run_cli(
        home,
        "skill",
        "starter",
        "--from-file",
        str(RELEASE_STARTER_SKILL),
    )

    assert obtained.exit_code == 0
    payload = obtained.envelope()["data"]
    assert payload["skill_root_digest"] == STARTER_SKILL_TREE_DIGEST
    assert payload["origin"] == "local_file"
