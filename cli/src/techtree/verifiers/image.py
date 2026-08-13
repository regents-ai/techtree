"""Asking the local daemon what the pinned subject image is. Decisions 0007 R5.

The evaluation cannot answer this. The pinned Verifiers build hands Docker an
image reference and records the reference, so its own output says what was
*asked for* and nothing about what was *there*. A comparison built on that alone
can only report the Campaign's own pin back to the reader, which is why the
image digest used to be a warning rather than a check.

So Techtree asks, once per variant, immediately before that variant's child is
launched. Two facts come back, both from the daemon:

*the content it holds* — ``docker image inspect`` resolves the pinned reference
or fails. A daemon that resolves ``repository@sha256:...`` is holding exactly
that content, and the repository digests it lists for the image are required to
include the pin, so a resolution that came from somewhere else is refused;

*the platform it serves* — the operating system and architecture the index was
resolved to on this host. The platform-specific manifest digest is *not* asked
of the daemon, because the daemon does not know it: an image pulled by index
digest keeps the index digest and the unpacked platform image, not the platform
manifest's own digest. That digest is a property of the pinned index, recorded
per platform in the Campaign, and read out by the platform observed here.

Nothing here pulls. Provisioning an image is an explicit setup step the operator
asks for (spec section 6.18), and an executor that downloaded a few hundred
megabytes to make its own check pass would be spending somebody's bandwidth to
avoid telling them the truth.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Iterable
from typing import Final

from techtree.errors import ValidationError
from techtree.models.base import JsonValue
from techtree.models.campaign import RuntimeSpec
from techtree.verifiers.models import SubjectImageResolution, VariantName

__all__ = [
    "IMAGE_INSPECT_TIMEOUT_SECONDS",
    "SUBJECT_IMAGE_UNRESOLVED",
    "resolve_subject_image",
]

#: Stable error code. Spec section 15.
SUBJECT_IMAGE_UNRESOLVED: Final = "subject_image_unresolved"

#: Inspecting a local image is a metadata read, but the daemon may still be
#: waking up.
IMAGE_INSPECT_TIMEOUT_SECONDS: Final = 30.0

_INSPECT_FORMAT: Final = "{{json .RepoDigests}}\t{{.Os}}/{{.Architecture}}"


def resolve_subject_image(
    runtime: RuntimeSpec, variant: VariantName
) -> SubjectImageResolution:
    """Return what this machine's daemon holds for the Campaign's subject image."""
    if shutil.which("docker") is None:
        raise ValidationError(
            "docker is not on PATH, so what the subject container would run "
            "cannot be established",
            code=SUBJECT_IMAGE_UNRESOLVED,
            details={"variant": variant.value, "image": runtime.image},
        )

    completed = subprocess.run(
        ["docker", "image", "inspect", runtime.image, "--format", _INSPECT_FORMAT],
        capture_output=True,
        text=True,
        check=False,
        timeout=IMAGE_INSPECT_TIMEOUT_SECONDS,
        stdin=subprocess.DEVNULL,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        raise ValidationError(
            f"the Docker daemon does not hold {runtime.image}; pull it as an "
            "explicit setup step before running an evaluation",
            code=SUBJECT_IMAGE_UNRESOLVED,
            details={
                "variant": variant.value,
                "image": runtime.image,
                "exit_code": completed.returncode,
            },
        )

    digests, _, platform = completed.stdout.strip().partition("\t")
    repository_digests = json.loads(digests)
    if runtime.image not in repository_digests:
        raise ValidationError(
            "the image the daemon resolved does not list the content the "
            "Campaign pinned among its own repository digests",
            code=SUBJECT_IMAGE_UNRESOLVED,
            details={
                "variant": variant.value,
                "image": runtime.image,
                "repository_digests": _text_detail(repository_digests),
            },
        )
    if platform not in runtime.image_platform_digests:
        raise ValidationError(
            f"the daemon serves {runtime.image} as {platform}, which the "
            "Campaign pins no manifest digest for",
            code=SUBJECT_IMAGE_UNRESOLVED,
            details={
                "variant": variant.value,
                "platform": platform,
                "pinned_platforms": _text_detail(runtime.image_platform_digests),
            },
        )

    return SubjectImageResolution(
        variant=variant,
        image=runtime.image,
        index_digest=runtime.image_index_digest,
        platform=platform,
    )


def _text_detail(values: Iterable[object]) -> list[JsonValue]:
    """Return an ordered, printable list in the shape error details carry."""
    return [text for text in sorted(str(value) for value in values)]
