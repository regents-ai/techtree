"""The subject image pin, re-read from the registry. Decisions 0007 R5.

Every Campaign this build generates pins its subject container by content: an
OCI image-index digest, and one platform-specific manifest digest for each
platform the Campaign supports. Those digests are constants in
:mod:`techtree.constants` because a generated artifact has to be byte-stable
offline, and a constant is exactly the kind of thing that quietly stops being
true.

So this suite asks the registry. It is preflight rather than a unit test for the
same reason ``test_verifiers_eval_contract`` is: it needs the network and a
Docker CLI, and it is the gate to run when a pin is bumped rather than something
every ``make check`` should depend on.

Nothing here pulls an image. ``docker manifest inspect`` reads the index's own
manifest list over the registry API, which is a few kilobytes of JSON.

    make verifiers-preflight
"""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any, Final

import pytest

from techtree.constants import (
    SUBJECT_IMAGE,
    SUBJECT_IMAGE_INDEX_DIGEST,
    SUBJECT_IMAGE_PLATFORM_DIGESTS,
    SUBJECT_IMAGE_REPOSITORY,
    SUBJECT_IMAGE_TAG,
)

pytestmark = pytest.mark.preflight

_TIMEOUT_SECONDS: Final = 120.0


def _docker(*arguments: str) -> str:
    """Run one Docker command, or skip when Docker cannot answer."""
    if shutil.which("docker") is None:
        pytest.skip("docker is not on PATH")
    completed = subprocess.run(
        ["docker", *arguments],
        capture_output=True,
        text=True,
        check=False,
        timeout=_TIMEOUT_SECONDS,
        stdin=subprocess.DEVNULL,
    )
    if completed.returncode != 0:
        pytest.fail(
            f"docker {' '.join(arguments)} exited {completed.returncode}: "
            f"{completed.stderr.strip()}"
        )
    return completed.stdout.strip()


@pytest.fixture(scope="module")
def index() -> dict[str, Any]:
    """The image index the pin names, as the registry serves it today."""
    document: dict[str, Any] = json.loads(_docker("manifest", "inspect", SUBJECT_IMAGE))
    return document


def test_the_pin_names_an_oci_image_index(index: dict[str, Any]) -> None:
    """The reference is an index, which is why a platform digest is needed."""
    assert index["mediaType"] == "application/vnd.oci.image.index.v1+json"
    assert f"{SUBJECT_IMAGE_REPOSITORY}@{SUBJECT_IMAGE_INDEX_DIGEST}" == SUBJECT_IMAGE


def test_every_pinned_platform_digest_is_the_one_the_index_lists(
    index: dict[str, Any],
) -> None:
    """The recorded per-platform manifests are the index's own.

    An OCI index lists attestation manifests beside the real ones, under the
    ``unknown/unknown`` platform. They are skipped by name rather than by
    position, because their position moves.
    """
    served = {
        f"{entry['platform']['os']}/{entry['platform']['architecture']}": entry[
            "digest"
        ]
        for entry in index["manifests"]
        if entry["platform"]["os"] != "unknown"
    }
    for platform, digest in SUBJECT_IMAGE_PLATFORM_DIGESTS.items():
        assert served.get(platform) == digest, (
            f"the registry now serves {platform} as {served.get(platform)}, "
            f"not {digest}"
        )


def test_the_tag_still_resolves_to_the_pinned_index(index: dict[str, Any]) -> None:
    """The tag the pin was taken from has not moved off it.

    A failure here is *not* a defect: a tag is expected to move, and the pin is
    what protects the Campaign from it. It is recorded as a check so that the
    day the tag moves is a day somebody knows about, rather than a surprise
    when a clean machine pulls by tag and gets something else.
    """
    tagged = json.loads(
        _docker(
            "manifest", "inspect", f"{SUBJECT_IMAGE_REPOSITORY}:{SUBJECT_IMAGE_TAG}"
        )
    )
    assert tagged == index, (
        f"{SUBJECT_IMAGE_REPOSITORY}:{SUBJECT_IMAGE_TAG} no longer resolves to "
        f"{SUBJECT_IMAGE_INDEX_DIGEST}; the pin still names the content the "
        "Campaign was validated against, and pulling by tag on a clean machine "
        "will now fetch something else"
    )
