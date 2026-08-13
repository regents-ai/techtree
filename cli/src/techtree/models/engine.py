"""The managed Verifiers engine. Spec 11.13, decisions 0003 A8/A9.

The engine is a locked, content-addressed bundle: a Python version, a pinned
Verifiers revision, and the reference packages, described by an
``EngineDescriptor``. The bundle's digest covers the static files and is not
stored inside the descriptor, because a document cannot contain its own hash.

Host platforms use one vocabulary — Go/OCI-style ``<os>/<arch>`` — everywhere
they appear. :func:`normalize_host_platform` is the only way a raw
``sys.platform`` and ``platform.machine()`` pair becomes one of those strings,
and it refuses rather than guesses on anything else. An unsupported host is a
prerequisite failure with a name, not an install that fails later for reasons
the user cannot read.

The engine's host platform and the subject runtime's Docker platform share this
vocabulary but remain separate concepts: one is where Techtree runs, the other
is where the evaluated agent runs, and they are frequently not the same
machine.
"""

from __future__ import annotations

from typing import Final, Literal, Self

from pydantic import model_validator

from techtree.errors import PrerequisiteError
from techtree.models.base import (
    Digest,
    NonEmptyString,
    ProtocolModel,
    StateModel,
    UtcDateTime,
)

__all__ = [
    "EngineDescriptor",
    "EngineInstallation",
    "EnginePackage",
    "EngineStatus",
    "HostPlatform",
    "normalize_host_platform",
]


type HostPlatform = Literal[
    "darwin/amd64",
    "darwin/arm64",
    "linux/amd64",
    "linux/arm64",
]
"""The complete host-platform vocabulary. Decisions document 0003 A9."""

#: Every machine string that means the same architecture. The keys are what
#: ``platform.machine()`` reports across the platforms Techtree supports.
_ARCHITECTURES: Final[dict[str, str]] = {
    "aarch64": "arm64",
    "amd64": "amd64",
    "arm64": "arm64",
    "x86_64": "amd64",
}

#: The closed vocabulary, keyed by the pair it is derived from. A table rather
#: than string concatenation, so that the only values this function can return
#: are the four the protocol defines.
_HOST_PLATFORMS: Final[dict[tuple[str, str], HostPlatform]] = {
    ("darwin", "amd64"): "darwin/amd64",
    ("darwin", "arm64"): "darwin/arm64",
    ("linux", "amd64"): "linux/amd64",
    ("linux", "arm64"): "linux/arm64",
}


def normalize_host_platform(sys_platform: str, machine: str) -> HostPlatform:
    """Return the ``<os>/<arch>`` name for a host, or refuse.

    Raises :class:`~techtree.errors.PrerequisiteError` for any combination
    outside the supported vocabulary. Guessing would produce an engine install
    that resolves wheels for the wrong architecture and fails much later,
    somewhere far less legible than here.
    """
    operating_system = sys_platform.strip().lower()
    architecture = _ARCHITECTURES.get(machine.strip().lower(), "")
    normalized = _HOST_PLATFORMS.get((operating_system, architecture))

    if normalized is None:
        raise PrerequisiteError(
            f"unsupported host platform {sys_platform}/{machine}; Techtree "
            "supports darwin and linux on arm64 and amd64",
            code="unsupported_host_platform",
            details={"sys_platform": sys_platform, "machine": machine},
        )
    return normalized


class EnginePackage(ProtocolModel):
    """One package shipped inside the engine bundle."""

    name: NonEmptyString
    version: NonEmptyString
    source_digest: Digest


class EngineDescriptor(ProtocolModel):
    """What one engine bundle is, without saying what it hashes to."""

    schema_version: Literal["techtree.engine.v1alpha1"]
    name: NonEmptyString
    python_version: NonEmptyString
    verifiers_version: NonEmptyString
    verifiers_revision: NonEmptyString
    supported_hosts: list[HostPlatform]
    packages: list[EnginePackage]

    @model_validator(mode="after")
    def _check_hosts_and_packages_are_listed_once(self) -> Self:
        """Reject an empty or repeating host or package list."""
        if not self.supported_hosts:
            raise ValueError("an engine must support at least one host platform")
        if len(set(self.supported_hosts)) != len(self.supported_hosts):
            raise ValueError("supported_hosts must not repeat a platform")
        names = [package.name for package in self.packages]
        if len(set(names)) != len(names):
            raise ValueError("an engine ships each package exactly once")
        return self


class EngineInstallation(StateModel):
    """A locally installed engine, as the registry records it."""

    digest: Digest
    installed_at: UtcDateTime
    python_executable: NonEmptyString
    descriptor_digest: Digest
    verified: bool


class EngineStatus(ProtocolModel):
    """What the CLI reports about one engine."""

    digest: Digest
    installed: bool
    active: bool
    verified: bool
    path: NonEmptyString
    python_executable: NonEmptyString | None
    detail: NonEmptyString

    @model_validator(mode="after")
    def _check_status_is_coherent(self) -> Self:
        """Reject a status that verifies or activates an engine that is absent."""
        if not self.installed and (self.verified or self.active):
            raise ValueError(
                "an engine that is not installed cannot be active or verified"
            )
        return self
