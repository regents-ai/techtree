"""Turning the static bundle into a working environment. Spec section 20.3.

Installing an engine means: materialize exactly the files the bundle digest
covers, build an isolated environment from the lock that shipped with them, ask
that environment what it actually is, and only then record it as installed.

Three properties are worth stating plainly.

*The lock is never regenerated here.* ``uv sync --frozen`` either agrees with
``uv.lock`` or fails. Resolving dependencies on a participant's machine would
mean each participant ran a slightly different engine, which would make the
digest a label rather than a guarantee.

*The global Python environment is irrelevant.* The engine has its own
interpreter and its own site-packages; nothing it runs is resolved through the
caller's ``PATH`` or the interpreter Techtree itself runs on.

*An installation is recorded only after the environment answers correctly.*
The verification query runs inside the engine and reports its Python version,
the Verifiers version and the exact commit it was built from, and where each
shipped package resolved on disk. Those are compared with the descriptor before
``installed.json`` is written, and ``installed.json`` is what makes the
directory count as an engine at all.

That last point is also how an interrupted install is safe. The environment is
built at its final content-addressed path — an editable path dependency and a
virtual environment both record absolute paths, so a directory built somewhere
else and moved afterwards is a broken environment, not a relocated one.
``installed.json``, written last, is the thing that says the directory is
finished; a directory without one is not an installation, and installing
replaces it.

Decisions document 0004, ratified as 0007 R7, adds the other half of that
protocol: an install *announces itself* before it starts. A ``.installing-``
marker is written into the engines directory before the engine directory is
created and removed only after ``installed.json`` exists, so a machine can
always tell the difference between the two reasons an engine might be absent.
An engine that was never installed leaves nothing behind. An install that was
killed — the power went, the terminal was closed, the machine rebooted mid-sync
— leaves a marker, and the next setup finds it, says so, and removes the
unfinished directory before building again rather than retrying on top of it.

The marker lives beside the engine directory rather than inside it, for two
reasons that are both about not disturbing what it protects: the bundle copy
requires an empty destination, and an installed engine's directory is hashed
file by file when it is verified. A marker inside would be either impossible to
write first or something the digest rule would have to be taught to ignore.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Final

from filelock import FileLock, Timeout

from techtree.canonical import digest_object
from techtree.engines.bundle import (
    DEFAULT_ENGINE_NAME,
    copy_engine_bundle,
    embedded_engine_root,
    engine_bundle_digest,
    read_engine_descriptor,
)
from techtree.engines.registry import EngineRegistry, digest_from_directory_name
from techtree.errors import (
    EngineError,
    PrerequisiteError,
    VerificationError,
)
from techtree.fs import (
    atomic_write_json,
    ensure_private_directory,
    fsync_directory,
    remove_tree,
)
from techtree.models.base import Digest
from techtree.models.engine import (
    EngineDescriptor,
    EngineInstallation,
    EngineStatus,
    normalize_host_platform,
)
from techtree.paths import TechtreePaths

__all__ = [
    "INSTALLING_MARKER_PREFIX",
    "INSTALL_LOCK_FILENAME",
    "SYNC_TIMEOUT_SECONDS",
    "VERIFICATION_TIMEOUT_SECONDS",
    "EngineInstaller",
    "EngineVerification",
    "InterruptedInstall",
    "find_uv",
]

#: A first install downloads several hundred megabytes of wheels, so this is
#: generous. It exists to end a hung network call, not to bound normal work.
SYNC_TIMEOUT_SECONDS: Final = 1800.0
#: Asking a built environment what it is imports Verifiers once.
VERIFICATION_TIMEOUT_SECONDS: Final = 300.0
#: One installer at a time per Techtree home.
INSTALL_LOCK_FILENAME: Final = ".install.lock"
INSTALL_LOCK_TIMEOUT_SECONDS: Final = 1800.0

#: Written before an install starts and removed after it publishes. The engine
#: directory's own name is appended, so one marker names one engine and a
#: reader can tell which install did not finish.
INSTALLING_MARKER_PREFIX: Final = ".installing-"

#: What a marker says, for a person reading a directory rather than for code.
#: Nothing branches on these values: the marker's *existence* is the signal, so
#: an unreadable marker still means exactly what a readable one means.
_MARKER_SCHEMA: Final = "techtree.engine-installing.v1"

#: Asked of the engine, answered by the engine. Written as one expression-free
#: script so it can be passed with ``-c`` and cannot import anything of
#: Techtree's: the whole point is that the engine speaks for itself.
_VERIFICATION_QUERY: Final = """\
import importlib, json, platform, sys
from importlib.metadata import distribution

modules = {}
for name in sys.argv[1:]:
    modules[name] = getattr(importlib.import_module(name), "__file__", None)

verifiers = distribution("verifiers")
recorded = json.loads(verifiers.read_text("direct_url.json") or "{}")

json.dump(
    {
        "python_version": platform.python_version(),
        "python_executable": sys.executable,
        "verifiers_version": verifiers.version,
        "verifiers_commit": recorded.get("vcs_info", {}).get("commit_id"),
        "modules": modules,
    },
    sys.stdout,
)
"""

#: How many characters of a failed command's output travel into an error.
#: Enough to name the cause, short enough not to turn a message into a log.
_OUTPUT_EXCERPT = 2000


@dataclass(frozen=True)
class EngineVerification:
    """What an installed engine says about itself."""

    python_version: str
    python_executable: str
    verifiers_version: str
    verifiers_commit: str
    modules: dict[str, str]


@dataclass(frozen=True)
class InterruptedInstall:
    """An install that announced itself and never published a result.

    ``started_at`` and ``pid`` come from the marker and are diagnostics only.
    A marker that cannot be read still describes an interrupted install; what
    is missing is only the ability to say when it started.
    """

    digest: Digest
    path: Path
    marker: Path
    started_at: str | None
    pid: int | None


class EngineInstaller:
    """Installs, verifies, and removes managed engines."""

    def __init__(
        self,
        paths: TechtreePaths,
        registry: EngineRegistry,
        uv_executable: Path,
    ) -> None:
        self._paths = paths
        self._registry = registry
        self._uv = uv_executable

    def install(self, digest: Digest | None = None) -> EngineStatus:
        """Materialize, frozen-sync, verify, and mark installed."""
        root = embedded_engine_root(DEFAULT_ENGINE_NAME)
        descriptor = read_engine_descriptor(root)
        bundle_digest = engine_bundle_digest(root)

        if digest is not None and digest != bundle_digest:
            raise EngineError(
                f"this build ships engine {bundle_digest}, not {digest}",
                code="engine_digest_unknown",
                details={"requested": digest, "available": bundle_digest},
            )

        _require_supported_host(descriptor)
        ensure_private_directory(self._paths.engines_dir)

        with self._install_lock():
            # Decisions 0004, ratified as 0007 R7: whatever a killed install
            # left behind goes before another one starts, so nothing is ever
            # built on top of a half-built environment.
            self.discard_interrupted()

            if self._registry.installation(bundle_digest) is not None:
                verified = self._verified_status(bundle_digest, descriptor)
                if verified is not None:
                    return verified
                # The directory exists but the environment inside it no longer
                # answers. There is nothing to preserve; build it again.
                remove_tree(self._registry.path(bundle_digest))

            return self._install_fresh(root, descriptor, bundle_digest)

    def interrupted_installs(self) -> list[InterruptedInstall]:
        """Report every engine whose install started and never published.

        A marker beside a complete installation is not one of these: the
        install finished and only the marker's removal was lost, so there is
        nothing unfinished to report and nothing to rebuild.
        """
        if not self._paths.engines_dir.is_dir():
            return []

        found: list[InterruptedInstall] = []
        for marker in sorted(self._paths.engines_dir.iterdir()):
            digest = _digest_from_marker_name(marker.name)
            if digest is None or not marker.is_file():
                continue
            if self._registry.installation(digest) is not None:
                continue
            started_at, pid = _read_marker(marker)
            found.append(
                InterruptedInstall(
                    digest=digest,
                    path=self._registry.path(digest),
                    marker=marker,
                    started_at=started_at,
                    pid=pid,
                )
            )
        return found

    def discard_interrupted(self) -> list[InterruptedInstall]:
        """Remove what unfinished installs left behind, and say what was there.

        Decisions 0004 step 5: a failed or interrupted install is removed
        rather than resumed. Half of a virtual environment is not a smaller
        engine — it is a directory whose contents nothing can vouch for — and
        the only honest thing to do with one is build it again.

        A marker left beside a *finished* install is dropped here too, in the
        other order: the installation is complete, so only the marker goes.
        """
        discarded = self.interrupted_installs()
        for install in discarded:
            remove_tree(install.path)
            _remove_marker(install.marker)
        for marker in self._stale_markers_of_complete_installs():
            _remove_marker(marker)
        return discarded

    def verify(self, digest: Digest) -> EngineStatus:
        """Verify the installed bundle and the live environment."""
        installation = self._registry.installation(digest)
        if installation is None:
            raise EngineError(
                f"engine {digest} is not installed",
                code="engine_not_installed",
                details={"digest": digest, "path": str(self._registry.path(digest))},
            )

        installed_root = self._registry.path(digest)
        recomputed = engine_bundle_digest(installed_root)
        if recomputed != digest:
            raise VerificationError(
                f"the files of engine {digest} have changed since it was "
                f"installed; they now hash to {recomputed}",
                code="engine_bundle_modified",
                details={"expected": digest, "recomputed": recomputed},
            )

        descriptor = read_engine_descriptor(installed_root)
        self._check_environment(digest, descriptor)
        return self._registry.status(digest)

    def uninstall(self, digest: Digest) -> None:
        """Remove an installed engine that is not the active one."""
        if self._registry.active_digest() == digest:
            raise EngineError(
                f"engine {digest} is active; activate another engine before "
                "removing it",
                code="engine_active",
                details={"digest": digest},
            )
        with self._install_lock():
            remove_tree(self._registry.path(digest))

    # -- steps -------------------------------------------------------------

    def _install_fresh(
        self,
        root: Traversable,
        descriptor: EngineDescriptor,
        digest: Digest,
    ) -> EngineStatus:
        """Build one engine from scratch at its content-addressed path."""
        destination = self._registry.path(digest)
        # Anything already here is the residue of an install that did not
        # finish, because a finished one would have been reused above.
        remove_tree(destination)

        # Written before the directory exists, so there is no moment where an
        # engine is being built and nothing on disk says so.
        marker = self._marker_path(digest)
        _write_marker(marker, digest)
        try:
            copy_engine_bundle(root, destination)
            self._sync(destination, descriptor)
            verification = self._check_environment(digest, descriptor)
        except BaseException:
            remove_tree(destination)
            _remove_marker(marker)
            raise

        self._registry.record(
            EngineInstallation(
                digest=digest,
                installed_at=datetime.now(UTC),
                python_executable=verification.python_executable,
                descriptor_digest=digest_object(descriptor),
                verified=True,
            )
        )
        # Last, and only after the one publication signal exists. A crash in
        # between leaves a marker beside a complete install, which the next
        # setup recognizes as residue rather than as unfinished work.
        _remove_marker(marker)
        return self._registry.status(digest)

    def _sync(self, destination: Path, descriptor: EngineDescriptor) -> None:
        """Build the engine environment from its own lock, and only from it.

        ``--frozen`` means the lock is the whole resolution: uv installs what it
        says and never writes a new one. A lock that is missing, unreadable, or
        does not cover the engine project is reported as its own failure,
        because it means the bundle is damaged rather than the network being
        unhappy — retrying would not help, reinstalling might.
        """
        completed = self._run(
            [
                str(self._uv),
                "sync",
                "--frozen",
                "--project",
                str(destination),
                "--python",
                descriptor.python_version,
            ],
            timeout=SYNC_TIMEOUT_SECONDS,
        )
        if completed.returncode == 0:
            return

        output = f"{completed.stdout}\n{completed.stderr}"
        if "uv.lock" in output or "lockfile" in output:
            raise EngineError(
                "the engine lock cannot be used with the engine project; the "
                f"engine files at {destination} are damaged or incomplete",
                code="engine_lock_mismatch",
                details={"path": str(destination), "detail": _excerpt(output)},
            )
        raise EngineError(
            f"building the engine environment failed: {_excerpt(completed.stderr)}",
            code="engine_sync_failed",
            details={"exit_code": completed.returncode},
            retryable=True,
        )

    def _check_environment(
        self, digest: Digest, descriptor: EngineDescriptor
    ) -> EngineVerification:
        """Ask the engine what it is, and refuse anything but the right answer."""
        verification = self._query(digest, descriptor)
        engine_root = self._registry.path(digest).resolve()

        _require(
            verification.python_version.startswith(f"{descriptor.python_version}."),
            f"engine runs Python {verification.python_version}, but the "
            f"descriptor pins {descriptor.python_version}",
            digest,
        )
        _require(
            verification.verifiers_version == descriptor.verifiers_version,
            f"engine holds Verifiers {verification.verifiers_version}, but the "
            f"descriptor pins {descriptor.verifiers_version}",
            digest,
        )
        _require(
            verification.verifiers_commit == descriptor.verifiers_revision,
            f"engine holds Verifiers commit {verification.verifiers_commit}, "
            f"but the descriptor pins {descriptor.verifiers_revision}",
            digest,
        )

        for package in descriptor.packages:
            location = verification.modules.get(_module_name(package.name))
            if location is None:
                raise EngineError(
                    f"package {package.name} did not report where it is installed",
                    code="engine_verification_mismatch",
                    details={"digest": digest, "package": package.name},
                )
            _require(
                Path(location).resolve().is_relative_to(engine_root),
                f"package {package.name} imports from {location}, which is "
                f"outside the engine at {engine_root}",
                digest,
            )

        return verification

    def _query(
        self, digest: Digest, descriptor: EngineDescriptor
    ) -> EngineVerification:
        """Run the verification query inside the engine."""
        python = self._registry.python(digest)
        if not python.is_file():
            raise EngineError(
                f"engine {digest} has no interpreter at {python}",
                code="engine_python_missing",
                details={"digest": digest, "path": str(python)},
            )

        modules = [_module_name(package.name) for package in descriptor.packages]
        completed = self._run(
            [str(python), "-c", _VERIFICATION_QUERY, *modules],
            timeout=VERIFICATION_TIMEOUT_SECONDS,
        )
        if completed.returncode != 0:
            raise EngineError(
                "the engine environment did not answer the verification query: "
                f"{_excerpt(completed.stderr)}",
                code="engine_verification_failed",
                details={"digest": digest, "exit_code": completed.returncode},
            )

        try:
            document = json.loads(completed.stdout)
            return EngineVerification(
                python_version=str(document["python_version"]),
                python_executable=str(document["python_executable"]),
                verifiers_version=str(document["verifiers_version"]),
                verifiers_commit=str(document["verifiers_commit"]),
                modules={
                    str(name): str(location)
                    for name, location in document["modules"].items()
                    if location is not None
                },
            )
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            raise EngineError(
                f"the engine verification query returned unusable output: {error}",
                code="engine_verification_unreadable",
                details={"digest": digest},
            ) from error

    def _verified_status(
        self, digest: Digest, descriptor: EngineDescriptor
    ) -> EngineStatus | None:
        """Return the status of an existing installation that still works."""
        try:
            self._check_environment(digest, descriptor)
        except EngineError:
            return None
        return self._registry.status(digest)

    def _marker_path(self, digest: Digest) -> Path:
        """Return where one engine's in-progress marker lives."""
        return (
            self._paths.engines_dir
            / f"{INSTALLING_MARKER_PREFIX}{self._registry.path(digest).name}"
        )

    def _stale_markers_of_complete_installs(self) -> list[Path]:
        """Return markers whose install finished after all."""
        if not self._paths.engines_dir.is_dir():
            return []
        return [
            marker
            for marker in sorted(self._paths.engines_dir.iterdir())
            if marker.is_file()
            and (digest := _digest_from_marker_name(marker.name)) is not None
            and self._registry.installation(digest) is not None
        ]

    @contextmanager
    def _install_lock(self) -> Iterator[None]:
        """Serialize installs within one Techtree home."""
        lock = FileLock(
            str(self._paths.engines_dir / INSTALL_LOCK_FILENAME),
            timeout=INSTALL_LOCK_TIMEOUT_SECONDS,
        )
        try:
            lock.acquire()
        except Timeout as error:
            raise EngineError(
                "another Techtree process is installing an engine",
                code="engine_install_locked",
                details={"path": str(self._paths.engines_dir)},
                retryable=True,
            ) from error
        try:
            yield
        finally:
            lock.release()

    def _run(
        self, argv: list[str], *, timeout: float
    ) -> subprocess.CompletedProcess[str]:
        """Run one installation command.

        Installation is the one place the caller's environment is passed
        through: uv needs the user's proxy, certificate, cache, and index
        configuration to reach a network the user can reach. Evaluation runs do
        not, and :mod:`techtree.engines.runner` gives them a minimal one.
        """
        try:
            return subprocess.run(
                argv,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
                stdin=subprocess.DEVNULL,
            )
        except subprocess.TimeoutExpired as error:
            raise EngineError(
                f"engine installation step timed out after {timeout:.0f}s",
                code="engine_install_timeout",
                details={"timeout_seconds": timeout},
                retryable=True,
            ) from error
        except OSError as error:
            raise EngineError(
                f"engine installation step could not be started: "
                f"{error.strerror or error}",
                code="engine_install_unusable",
                details={"argv0": argv[0]},
            ) from error


def _write_marker(marker: Path, digest: Digest) -> None:
    """Announce an install, durably, before anything is built."""
    atomic_write_json(
        marker,
        {
            "schema_version": _MARKER_SCHEMA,
            "digest": digest,
            "started_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "pid": os.getpid(),
        },
    )


def _remove_marker(marker: Path) -> None:
    """Withdraw an announcement, and make the removal durable."""
    marker.unlink(missing_ok=True)
    fsync_directory(marker.parent)


def _read_marker(marker: Path) -> tuple[str | None, int | None]:
    """Return what a marker says about its install, when it can say anything."""
    try:
        document = json.loads(marker.read_bytes())
    except (OSError, ValueError):
        return None, None
    if not isinstance(document, dict):
        return None, None
    started_at = document.get("started_at")
    pid = document.get("pid")
    return (
        started_at if isinstance(started_at, str) else None,
        pid if isinstance(pid, int) else None,
    )


def _digest_from_marker_name(name: str) -> Digest | None:
    """Return the engine digest one marker names, or None if it names none."""
    if not name.startswith(INSTALLING_MARKER_PREFIX):
        return None
    return digest_from_directory_name(name[len(INSTALLING_MARKER_PREFIX) :])


def find_uv() -> Path:
    """Locate uv, or say what is missing."""
    found = shutil.which("uv")
    if found is None:
        raise EngineError(
            "uv was not found on PATH; the managed evaluation engine is "
            "installed with uv (https://docs.astral.sh/uv/getting-started/"
            "installation/)",
            code="uv_not_found",
            retryable=True,
        )
    return Path(found)


def _require_supported_host(descriptor: EngineDescriptor) -> None:
    """Refuse to install an engine that does not support this machine."""
    try:
        host = normalize_host_platform(sys.platform, platform.machine())
    except PrerequisiteError as error:
        raise EngineError(
            str(error),
            code="engine_host_unsupported",
            details=dict(error.details),
        ) from error

    if host not in descriptor.supported_hosts:
        raise EngineError(
            f"the managed engine does not support {host}; it supports "
            + ", ".join(descriptor.supported_hosts),
            code="engine_host_unsupported",
            details={
                "host_platform": host,
                "supported_hosts": list(descriptor.supported_hosts),
            },
        )


def _module_name(distribution_name: str) -> str:
    """Return the module a distribution imports as.

    Verifiers resolves a local taskset id to a module by replacing hyphens with
    underscores (``docs/verifiers-pin.md``), and the shipped packages follow
    the same rule.
    """
    return distribution_name.replace("-", "_")


def _require(condition: bool, message: str, digest: Digest) -> None:
    if condition:
        return
    raise EngineError(
        message,
        code="engine_verification_mismatch",
        details={"digest": digest},
    )


def _excerpt(output: str) -> str:
    """Return the tail of a command's output, which is where the reason is.

    Installation is the one step that runs a subprocess with the caller's own
    environment (see :meth:`_EngineInstaller._run`), so uv's output can quote
    the caller's own configuration back. It is repeated word for word:
    decision 0036 rules that Techtree does not guess at what a borrowed line
    means before writing it down.
    """
    text = output.strip()
    if len(text) <= _OUTPUT_EXCERPT:
        return text
    return f"...{text[-_OUTPUT_EXCERPT:]}"
