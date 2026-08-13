"""Which engines exist, where they live, and which one is active.

Spec section 20.4.

An engine is identified by the digest of its static bundle, and that digest is
also where it lives: ``<techtree home>/engines/sha256-<hex>/``. Two consequences
follow, and both are the point.

Nothing here decides anything about *content*. The registry answers questions
about the filesystem and about settings; whether the environment inside an
engine actually works is the installer's question, asked by running the engine.

An engine counts as installed only when its ``installed.json`` is present,
parses, and names the directory it sits in. That file is written last, after
verification, so a directory left behind by an interrupted install is reported
as absent rather than as broken — and the next install replaces it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from techtree.canonical import validate_digest
from techtree.engines.bundle import (
    ENGINE_TOOLS,
    INSTALLATION_FILENAME,
    default_engine_digest,
)
from techtree.errors import EngineError, NotFoundError, ValidationError
from techtree.fs import atomic_write_json
from techtree.models.base import Digest
from techtree.models.engine import EngineInstallation, EngineStatus
from techtree.paths import TechtreePaths
from techtree.settings import Settings, load_settings, save_settings

__all__ = ["VENV_DIRECTORY", "EngineRegistry"]

#: uv's project environment, relative to the engine root.
VENV_DIRECTORY: Final = ".venv"
_BIN_DIRECTORY: Final = "bin"
_TOOLS_DIRECTORY: Final = "tools"


class EngineRegistry:
    """Locates engines and records which one is active."""

    def __init__(self, paths: TechtreePaths, settings: Settings) -> None:
        self._paths = paths
        self._settings = settings

    # -- what exists ------------------------------------------------------

    def known(self) -> list[Digest]:
        """Return the packaged digest and every installed digest."""
        digests = {default_engine_digest(), *self.installed()}
        return sorted(digests)

    def installed(self) -> list[Digest]:
        """Return the digests of complete installations."""
        if not self._paths.engines_dir.is_dir():
            return []

        found: list[Digest] = []
        for directory in sorted(self._paths.engines_dir.iterdir()):
            if not directory.is_dir():
                continue
            digest = _digest_from_directory_name(directory.name)
            if digest is None:
                continue
            if self.installation(digest) is not None:
                found.append(digest)
        return found

    def installation(self, digest: Digest) -> EngineInstallation | None:
        """Return the recorded installation, or None when there is not one.

        A record that does not name this directory is not this engine's record,
        so it is treated as absent rather than trusted.
        """
        marker = self.path(digest) / INSTALLATION_FILENAME
        try:
            raw = marker.read_bytes()
        except (FileNotFoundError, NotADirectoryError):
            return None

        try:
            installation = EngineInstallation.model_validate_json(raw)
        except ValueError:
            return None

        if installation.digest != digest:
            return None
        return installation

    def record(self, installation: EngineInstallation) -> None:
        """Write the installation marker that completes an install."""
        atomic_write_json(
            self.path(installation.digest) / INSTALLATION_FILENAME, installation
        )

    # -- where things are -------------------------------------------------

    def path(self, digest: Digest) -> Path:
        """Return the installation directory for one engine."""
        return self._paths.engine_dir(validate_digest(digest))

    def python(self, digest: Digest) -> Path:
        """Return the engine's managed interpreter."""
        return self.path(digest) / VENV_DIRECTORY / _BIN_DIRECTORY / "python"

    def executable(self, digest: Digest, name: str) -> Path:
        """Return one console script inside the engine environment.

        The pinned Verifiers build installs its scripts under generic names —
        ``validate``, ``eval`` — so they are always addressed by absolute path
        inside the engine and never resolved through ``PATH``
        (``docs/verifiers-pin.md``, finding C3).
        """
        return self.path(digest) / VENV_DIRECTORY / _BIN_DIRECTORY / _plain(name)

    def tool_path(self, digest: Digest, tool: str) -> Path:
        """Return one engine helper shipped inside the bundle.

        Decisions document 0003 A3. Only the helpers the bundle declares can be
        addressed, so a caller cannot turn this into "run any file you like
        with the engine interpreter".
        """
        if tool not in ENGINE_TOOLS:
            raise NotFoundError(
                f"the engine bundle ships no tool named {tool!r}",
                code="engine_tool_unknown",
                details={"tool": tool, "available": list(ENGINE_TOOLS)},
            )
        return self.path(digest) / _TOOLS_DIRECTORY / tool

    # -- status and activation --------------------------------------------

    def status(self, digest: Digest) -> EngineStatus:
        """Return what is currently true about one engine."""
        installation = self.installation(digest)
        active = self.active_digest() == digest

        if installation is None:
            return EngineStatus(
                digest=digest,
                installed=False,
                active=False,
                verified=False,
                path=str(self.path(digest)),
                python_executable=None,
                detail=_absent_detail(digest, active=active),
            )

        return EngineStatus(
            digest=digest,
            installed=True,
            active=active,
            verified=installation.verified,
            path=str(self.path(digest)),
            python_executable=installation.python_executable,
            detail=_present_detail(installation.verified, active=active),
        )

    def active_digest(self) -> Digest | None:
        """Return the digest of the active engine, if one is recorded."""
        return self._settings.active_engine_digest

    def set_active(self, digest: Digest) -> Settings:
        """Record one verified engine as active.

        Activation is a claim the CLI makes to every later command, so it is
        refused unless the engine is installed and its installation was
        verified. Verification itself belongs to the installer, which runs the
        engine; this reads the result it recorded.
        """
        installation = self.installation(validate_digest(digest))
        if installation is None:
            raise EngineError(
                f"engine {digest} is not installed, so it cannot be made active",
                code="engine_not_installed",
                details={"digest": digest, "path": str(self.path(digest))},
            )
        if not installation.verified:
            raise EngineError(
                f"engine {digest} was never verified, so it cannot be made active",
                code="engine_not_verified",
                details={"digest": digest},
            )

        # Settings are re-read rather than written from this object's copy, so
        # concurrently changed preferences are not reverted by an activation.
        settings = load_settings(self._paths).model_copy(
            update={"active_engine_digest": digest}
        )
        save_settings(self._paths, settings)
        self._settings = settings
        return settings


def _plain(name: str) -> str:
    """Reject anything that is not a bare file name."""
    if not name or "/" in name or name in {".", ".."}:
        raise EngineError(
            f"{name!r} is not an engine executable name",
            code="engine_executable_invalid",
            details={"name": name},
        )
    return name


def _digest_from_directory_name(name: str) -> Digest | None:
    """Return the digest a directory name encodes, or None if it encodes none."""
    algorithm, separator, hexadecimal = name.partition("-")
    if separator != "-" or algorithm != "sha256":
        return None
    candidate = f"{algorithm}:{hexadecimal}"
    try:
        return validate_digest(candidate)
    except ValidationError:
        return None


def _absent_detail(digest: Digest, *, active: bool) -> str:
    if active:
        return (
            f"engine {digest} is recorded as active but is not installed; "
            "install it again"
        )
    return "not installed"


def _present_detail(verified: bool, *, active: bool) -> str:
    state = "installed and verified" if verified else "installed but not verified"
    return f"{state}, {'active' if active else 'not the active engine'}"
