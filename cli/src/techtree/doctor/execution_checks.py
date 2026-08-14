"""What has to be true before a real evaluation starts. Spec section 6.18.

:mod:`techtree.doctor.checks` answers "is this machine usable at all". This
module answers a narrower and more expensive question: could the *next* real
Campaign run actually execute here. The two are separate because the answers
have different consequences. Somebody browsing Climbs should not be told that
Docker is broken as though the tool were unusable; somebody about to spend money
on model calls should be stopped before a container is provisioned.

Three distinctions run through the whole module.

*The subject platform is not the host platform.* An evaluated subject runs in a
container on whatever the daemon serves, which on macOS is a Linux VM. Both are
reported in one ``<os>/<arch>`` vocabulary so a Campaign's declared
``supported_platforms`` can be compared against the thing that will actually run
it, rather than against the laptop.

*Evaluation authentication is not host authentication.* The credential checked
here buys tokens for the evaluated subject. It has nothing to do with whatever
the operator's own Hermes is signed in with, and it fails late and expensively
if it is missing: the pinned client resolves an absent key to the literal string
``"EMPTY"`` and only discovers the problem at the first model call, after Docker
is up (``docs/verifiers-eval.md``). It is also diagnosed for the environment a
detached run would be given rather than for the terminal these checks were
typed into, because those differ in the one way that matters and a readiness
answer that cannot survive the difference is worse than no answer at all.

*Pulling an image is a setup operation, not a check.* A check that silently
downloaded gigabytes would be a check that lied about being read-only.
:func:`check_subject_image` inspects what is present locally and says plainly
what to run when it is not.

Nothing here reads or returns a credential value; see
:mod:`techtree.verifiers.credentials` for why that is a hard boundary rather
than a habit.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Final

from techtree.doctor.checks import (
    DAEMON_TIMEOUT_SECONDS,
    VERSION_TIMEOUT_SECONDS,
    detect_host_platform,
)
from techtree.engines.bundle import read_engine_descriptor
from techtree.engines.registry import EngineRegistry
from techtree.errors import ValidationError
from techtree.models.base import Digest, JsonValue
from techtree.models.campaign import (
    SUBJECT_AGENT,
    CampaignSpec,
    ModelSpec,
    RuntimeSpec,
)
from techtree.models.cli import CheckStatus, DoctorCheck
from techtree.runs.launcher import worker_visible_environment
from techtree.verifiers.child import EVAL_EXECUTABLE
from techtree.verifiers.credentials import credential_status
from techtree.verifiers.image import resolve_subject_image
from techtree.verifiers.models import VariantName

__all__ = [
    "DEVELOPMENT_PLACEHOLDER_MARKERS",
    "IMAGE_INSPECT_TIMEOUT_SECONDS",
    "check_docker_platform",
    "check_engine_eval",
    "check_live_campaign",
    "check_prime_auth",
    "check_subject_image",
    "execution_checks",
]

#: Inspecting a local image is a metadata read, but the daemon may still be
#: waking up, so it gets the daemon's allowance rather than a version probe's.
IMAGE_INSPECT_TIMEOUT_SECONDS: Final = DAEMON_TIMEOUT_SECONDS

#: Substrings that mark a Campaign as a development fixture rather than
#: something that may be executed for real. The shipped Campaign's subject model
#: is still one of these, so a real run must not start from it until the founder
#: ratifies the release coordinates. Its container is not: decisions document
#: 0007 R5 pins the image by content, which is a fact about a registry rather
#: than a coordinate anybody ratifies. Every field is still scanned, because
#: which fields happen to carry a placeholder today is not what the check is
#: about.
DEVELOPMENT_PLACEHOLDER_MARKERS: Final[tuple[str, ...]] = (
    "development-placeholder",
    "not-executed",
)

#: The platform strings a subject container can be served on.
_SUPPORTED_SUBJECT_PLATFORMS: Final[tuple[str, ...]] = ("linux/arm64", "linux/amd64")


def check_docker_platform() -> DoctorCheck:
    """Confirm the daemon is reachable and serving a supported subject platform."""
    metadata: dict[str, JsonValue] = {"host_platform": detect_host_platform()}

    if shutil.which("docker") is None:
        return DoctorCheck(
            id="execution_docker_platform",
            label="Docker subject platform",
            status=CheckStatus.FAIL,
            detail=(
                "docker was not found on PATH; an evaluated subject runs in a "
                "container on this host"
            ),
            blocking=True,
            metadata=metadata,
        )

    served = _docker_platform()
    if served is None:
        return DoctorCheck(
            id="execution_docker_platform",
            label="Docker subject platform",
            status=CheckStatus.FAIL,
            detail=(
                "the Docker daemon did not answer; start Docker before running "
                "an evaluation"
            ),
            blocking=True,
            metadata=metadata,
        )

    metadata["docker_platform"] = served
    if served not in _SUPPORTED_SUBJECT_PLATFORMS:
        return DoctorCheck(
            id="execution_docker_platform",
            label="Docker subject platform",
            status=CheckStatus.FAIL,
            detail=(
                f"the Docker daemon serves {served}; an evaluated subject needs "
                f"one of {', '.join(_SUPPORTED_SUBJECT_PLATFORMS)}"
            ),
            blocking=True,
            metadata=metadata,
        )

    return DoctorCheck(
        id="execution_docker_platform",
        label="Docker subject platform",
        status=CheckStatus.PASS,
        detail=f"the Docker daemon is reachable and serving {served}",
        blocking=False,
        metadata=metadata,
    )


def check_engine_eval(
    engine_registry: EngineRegistry, digest: Digest | None = None
) -> DoctorCheck:
    """Confirm the engine's own ``eval`` exists and holds the expected revision.

    The console script is addressed by absolute path inside the engine's virtual
    environment. Checking that the file is there is checking the one thing a
    real run cannot recover from: a ``PATH`` lookup would find *something*
    called ``eval`` on almost any machine.
    """
    resolved = digest if digest is not None else engine_registry.active_digest()
    metadata: dict[str, JsonValue] = {"engine_digest": resolved}

    if resolved is None:
        return DoctorCheck(
            id="execution_engine_eval",
            label="Engine eval entrypoint",
            status=CheckStatus.FAIL,
            detail=(
                "no managed evaluation engine is active; install one before "
                "running an evaluation"
            ),
            blocking=True,
            metadata=metadata,
        )

    status = engine_registry.status(resolved)
    if not status.installed:
        return DoctorCheck(
            id="execution_engine_eval",
            label="Engine eval entrypoint",
            status=CheckStatus.FAIL,
            detail=f"engine {resolved} is not installed",
            blocking=True,
            metadata=metadata,
        )
    if not status.verified:
        return DoctorCheck(
            id="execution_engine_eval",
            label="Engine eval entrypoint",
            status=CheckStatus.FAIL,
            detail=(
                f"engine {resolved} is installed but has not been verified; a "
                "real run executes only a verified engine"
            ),
            blocking=True,
            metadata=metadata,
        )

    executable = engine_registry.executable(resolved, EVAL_EXECUTABLE)
    metadata["eval_executable"] = str(executable)
    if not executable.is_file():
        return DoctorCheck(
            id="execution_engine_eval",
            label="Engine eval entrypoint",
            status=CheckStatus.FAIL,
            detail=(
                f"engine {resolved} has no {EVAL_EXECUTABLE} entrypoint at "
                f"{executable}; install the engine again"
            ),
            blocking=True,
            metadata=metadata,
        )

    descriptor = read_engine_descriptor(engine_registry.path(resolved))
    metadata["verifiers_version"] = descriptor.verifiers_version
    metadata["verifiers_revision"] = descriptor.verifiers_revision
    return DoctorCheck(
        id="execution_engine_eval",
        label="Engine eval entrypoint",
        status=CheckStatus.PASS,
        detail=(
            f"{executable} is present, holding Verifiers "
            f"{descriptor.verifiers_version} at {descriptor.verifiers_revision}"
        ),
        blocking=False,
        metadata=metadata,
    )


def check_prime_auth(model: ModelSpec) -> DoctorCheck:
    """Confirm a run could authenticate, without reading anything.

    The question is asked about the environment a detached run would be given,
    not about the terminal this check was typed into. Those differ in exactly
    one way that matters: a credential exported in a terminal is not among the
    variables a run inherits, so a check that consulted its own environment
    could report "ready" about a run that stops at its first model call. When
    the export is there and unusable the check says so, because a person who
    exported it has every reason to expect it to count.
    """
    status = credential_status(model, environ=worker_visible_environment())
    exported = bool(os.environ.get(model.credential_env))
    detail = status.detail
    if not status.available and exported:
        detail = (
            f"{model.credential_env} is set in this terminal, but a run works in "
            "a separate background process that is not given this terminal's "
            f"variables, so nothing exported here can reach it: {detail}"
        )
    return DoctorCheck(
        id="execution_model_credential",
        label="Evaluation model credential",
        status=CheckStatus.PASS if status.available else CheckStatus.FAIL,
        detail=detail,
        blocking=not status.available,
        metadata={
            "provider": status.provider,
            "model_id": model.model_id,
            "credential_env": status.credential_env,
            "source": status.source,
            "exported_in_this_terminal": exported,
        },
    )


def check_subject_image(runtime: RuntimeSpec) -> DoctorCheck:
    """Report whether the pinned subject image is on this machine, as pinned.

    Absent is a failure with an argument vector attached, not a prompt to pull.
    Downloading an image is an explicit setup operation the operator asks for
    (spec section 6.18); a check that did it silently would spend somebody's
    bandwidth to make its own answer come out right.

    Present-but-different is a failure too. The Campaign pins the image by
    content and pins one manifest digest per platform it supports, so a daemon
    holding something else, or serving the pin on a platform the Campaign never
    recorded, cannot run this Campaign — and finding that out here is much
    cheaper than finding it out from a comparison that has already been paid
    for.
    """
    metadata: dict[str, JsonValue] = {"image": runtime.image}

    try:
        resolution = resolve_subject_image(runtime, VariantName.BASELINE)
    except ValidationError as refusal:
        return DoctorCheck(
            id="execution_subject_image",
            label="Subject runtime image",
            status=CheckStatus.FAIL,
            detail=refusal.message,
            blocking=True,
            metadata={**metadata, "pull": f"docker pull {runtime.image}"},
        )

    metadata["image_platform"] = resolution.platform
    metadata["image_platform_digest"] = runtime.image_platform_digests[
        resolution.platform
    ]
    return DoctorCheck(
        id="execution_subject_image",
        label="Subject runtime image",
        status=CheckStatus.PASS,
        detail=(
            f"the daemon holds the pinned subject image and serves it as "
            f"{resolution.platform}, which the Campaign pins a manifest digest "
            "for"
        ),
        blocking=False,
        metadata=metadata,
    )


def check_live_campaign(campaign: CampaignSpec) -> DoctorCheck:
    """Refuse a Campaign whose coordinates are development placeholders.

    The shipped Campaign names a model that exists to be compiled and dry-run,
    never to be executed. Catching that here is the difference between a clear
    refusal and a container that starts, authenticates against nothing, and
    fails at the first model call.
    """
    subject = campaign.agents.get(SUBJECT_AGENT)
    metadata: dict[str, JsonValue] = {"campaign_id": campaign.metadata.id}

    if subject is None:
        return DoctorCheck(
            id="execution_live_campaign",
            label="Campaign is executable",
            status=CheckStatus.FAIL,
            detail=f"the Campaign defines no {SUBJECT_AGENT!r} agent to execute",
            blocking=True,
            metadata=metadata,
        )

    metadata["model_id"] = subject.model.model_id
    metadata["provider"] = subject.model.provider
    metadata["image"] = subject.runtime.image

    placeholders = sorted(
        {
            f"{field}={value}"
            for field, value in (
                ("provider", subject.model.provider),
                ("model_id", subject.model.model_id),
                ("image", subject.runtime.image),
            )
            for marker in DEVELOPMENT_PLACEHOLDER_MARKERS
            if marker in value
        }
    )
    if placeholders:
        return DoctorCheck(
            id="execution_live_campaign",
            label="Campaign is executable",
            status=CheckStatus.FAIL,
            detail=(
                "this Campaign carries development placeholders and must not be "
                f"executed for real: {', '.join(placeholders)}"
            ),
            blocking=True,
            metadata=metadata,
        )

    return DoctorCheck(
        id="execution_live_campaign",
        label="Campaign is executable",
        status=CheckStatus.PASS,
        detail=(
            f"the Campaign names a real subject: {subject.model.model_id} on "
            f"{subject.runtime.image}"
        ),
        blocking=False,
        metadata=metadata,
    )


def execution_checks(
    *,
    engine_registry: EngineRegistry,
    campaign: CampaignSpec | None = None,
    engine_digest: Digest | None = None,
) -> list[DoctorCheck]:
    """Run every execution check, in a deterministic order.

    Without a Campaign only the machine-level questions can be asked, which is
    the honest answer for ``techtree doctor --for-evaluation`` run before a
    Climb has been chosen.
    """
    checks = [
        check_docker_platform(),
        check_engine_eval(engine_registry, engine_digest),
    ]
    if campaign is None:
        return checks

    checks.append(check_live_campaign(campaign))
    subject = campaign.agents.get(SUBJECT_AGENT)
    if subject is not None:
        checks.append(check_prime_auth(subject.model))
        checks.append(check_subject_image(subject.runtime))
    return checks


def _docker_platform() -> str | None:
    """Return the ``<os>/<arch>`` the daemon serves, or None if it did not answer."""
    return _run(
        ["docker", "version", "--format", "{{.Server.Os}}/{{.Server.Arch}}"],
        timeout=DAEMON_TIMEOUT_SECONDS,
    )


def _run(argv: list[str], *, timeout: float = VERSION_TIMEOUT_SECONDS) -> str | None:
    """Run one argument vector and return its first line of output, or None."""
    executable = shutil.which(argv[0])
    if executable is None:
        return None
    try:
        completed = subprocess.run(
            [executable, *argv[1:]],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            stdin=subprocess.DEVNULL,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if completed.returncode != 0:
        return None
    for line in completed.stdout.splitlines():
        if line.strip():
            return line.strip()
    return None
