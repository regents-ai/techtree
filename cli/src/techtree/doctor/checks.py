"""One function per thing that can be wrong with a host. Spec section 13.1.

Each check answers a single question and returns a :class:`~techtree.models.
cli.DoctorCheck` whether the answer is good or bad. No check raises: a Doctor
that stops at the first problem tells you about one problem, and the point of
Doctor is to tell you about all of them at once.

``blocking`` is a claim about *this* moment, not about the tool in general.
Python and a usable Techtree home block everything, so a failure there blocks.
uv blocks engine setup and nothing else, so an ordinary Doctor reports it as a
warning and says what it will block. Docker and Hermes are warnings before the
subject and host-agent work packages exist.

Two platform strings appear here and they are different things. The *host*
platform is where Techtree itself runs. The *Docker* platform is where an
evaluated subject would run, reported by the daemon, and frequently not the
same machine. Both use the one ``<os>/<arch>`` vocabulary so they can be
compared, and Doctor shows both rather than implying one from the other.

Every external tool is invoked as an argument vector with a timeout and with
stdin closed. No shell is involved, so nothing here can be influenced by what a
directory happens to be called, and no probe can block on a prompt.
"""

from __future__ import annotations

import os
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Final

from techtree.errors import PrerequisiteError
from techtree.models.base import JsonValue
from techtree.models.catalog import EngineCompatibilityStatus
from techtree.models.cli import CheckStatus, DoctorCheck
from techtree.models.engine import normalize_host_platform
from techtree.paths import TechtreePaths
from techtree.settings import Settings

__all__ = [
    "DAEMON_TIMEOUT_SECONDS",
    "SUPPORTED_PYTHON",
    "VERSION_TIMEOUT_SECONDS",
    "check_active_engine",
    "check_docker_cli",
    "check_docker_daemon",
    "check_hermes_cli",
    "check_host_platform",
    "check_python_version",
    "check_techtree_home",
    "check_uv_cli",
    "detect_host_platform",
]

#: Asking a tool for its version is a local operation. Anything slower than
#: this is a broken installation, not a slow one.
VERSION_TIMEOUT_SECONDS: Final = 10.0
#: Reaching the Docker daemon can involve starting a VM on macOS, so it gets
#: more room than a version probe.
DAEMON_TIMEOUT_SECONDS: Final = 20.0

#: The interpreter range the project declares. Kept as a pair of tuples so the
#: comparison is on version numbers rather than on strings.
SUPPORTED_PYTHON: Final[tuple[tuple[int, int], tuple[int, int]]] = ((3, 12), (3, 14))

#: Techtree state is single-user. Anything more permissive is worth saying out
#: loud without refusing to work.
_PRIVATE_DIRECTORY_MODE: Final = 0o700


@dataclass(frozen=True)
class _Probe:
    """What running one external tool told us."""

    executable: str | None
    exit_code: int | None
    output: str
    timed_out: bool

    @property
    def found(self) -> bool:
        """Whether the executable exists on PATH at all."""
        return self.executable is not None

    @property
    def succeeded(self) -> bool:
        """Whether the tool ran and reported success."""
        return self.exit_code == 0


def _probe(argv: list[str], *, timeout: float) -> _Probe:
    """Run one argument vector with stdin closed and a hard timeout."""
    executable = shutil.which(argv[0])
    if executable is None:
        return _Probe(executable=None, exit_code=None, output="", timed_out=False)

    try:
        completed = subprocess.run(
            [executable, *argv[1:]],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return _Probe(executable=executable, exit_code=None, output="", timed_out=True)
    except OSError as error:
        return _Probe(
            executable=executable,
            exit_code=None,
            output=str(error.strerror or error),
            timed_out=False,
        )

    return _Probe(
        executable=executable,
        exit_code=completed.returncode,
        output=_first_line(completed.stdout) or _first_line(completed.stderr),
        timed_out=False,
    )


def _first_line(text: str) -> str:
    """Return the first non-blank line, which is where tools put the answer."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def detect_host_platform() -> str | None:
    """Return the normalized ``<os>/<arch>`` host name, or None if unsupported."""
    try:
        return normalize_host_platform(sys.platform, platform.machine())
    except PrerequisiteError:
        return None


def check_python_version() -> DoctorCheck:
    """Require Python >=3.12,<3.14."""
    version = platform.python_version()
    minimum, exclusive_maximum = SUPPORTED_PYTHON
    running = sys.version_info[:2]
    supported = minimum <= running < exclusive_maximum

    if supported:
        detail = f"Python {version}"
    else:
        detail = (
            f"Python {version} is outside the supported range "
            f">={minimum[0]}.{minimum[1]},"
            f"<{exclusive_maximum[0]}.{exclusive_maximum[1]}"
        )

    return DoctorCheck(
        id="python_version",
        label="Python version",
        status=CheckStatus.PASS if supported else CheckStatus.FAIL,
        detail=detail,
        blocking=not supported,
        metadata={"python_version": version, "executable": sys.executable},
    )


def check_host_platform(host_platform: str | None) -> DoctorCheck:
    """Report the normalized host platform Techtree is running on."""
    if host_platform is None:
        return DoctorCheck(
            id="host_platform",
            label="Host platform",
            status=CheckStatus.FAIL,
            detail=(
                f"{sys.platform}/{platform.machine()} is not a supported host; "
                "Techtree supports darwin and linux on arm64 and amd64"
            ),
            blocking=True,
            metadata={"sys_platform": sys.platform, "machine": platform.machine()},
        )

    return DoctorCheck(
        id="host_platform",
        label="Host platform",
        status=CheckStatus.PASS,
        detail=host_platform,
        blocking=False,
        metadata={"host_platform": host_platform},
    )


def check_techtree_home(paths: TechtreePaths) -> DoctorCheck:
    """Check creation, writeability, and private permissions."""
    root = paths.root
    metadata: dict[str, JsonValue] = {"path": str(root)}

    if not root.is_dir():
        return DoctorCheck(
            id="techtree_home",
            label="Techtree home",
            status=CheckStatus.FAIL,
            detail=f"{root} does not exist as a directory",
            blocking=True,
            metadata={"path": str(root)},
        )

    try:
        with tempfile.NamedTemporaryFile(dir=root, prefix=".doctor-", suffix=".probe"):
            pass
    except OSError as error:
        return DoctorCheck(
            id="techtree_home",
            label="Techtree home",
            status=CheckStatus.FAIL,
            detail=f"{root} is not writable: {error.strerror or error}",
            blocking=True,
            metadata={"path": str(root)},
        )

    mode = stat.S_IMODE(os.stat(root).st_mode)
    metadata["mode"] = f"0o{mode:03o}"

    if mode != _PRIVATE_DIRECTORY_MODE:
        return DoctorCheck(
            id="techtree_home",
            label="Techtree home",
            status=CheckStatus.WARN,
            detail=(
                f"{root} is writable but its permissions are 0o{mode:03o}; "
                "Techtree state is single-user and should be 0o700"
            ),
            blocking=False,
            metadata=dict(metadata),
        )

    return DoctorCheck(
        id="techtree_home",
        label="Techtree home",
        status=CheckStatus.PASS,
        detail=f"{root} is writable and private",
        blocking=False,
        metadata=dict(metadata),
    )


def check_uv_cli() -> DoctorCheck:
    """Find uv and report version."""
    probe = _probe(["uv", "--version"], timeout=VERSION_TIMEOUT_SECONDS)

    if not probe.found:
        return DoctorCheck(
            id="uv",
            label="uv",
            status=CheckStatus.WARN,
            detail=(
                "uv was not found on PATH; installing the managed evaluation "
                "engine requires it"
            ),
            blocking=False,
            metadata={},
        )

    if not probe.succeeded:
        return DoctorCheck(
            id="uv",
            label="uv",
            status=CheckStatus.WARN,
            detail=_probe_failure_detail("uv", probe),
            blocking=False,
            metadata={"executable": probe.executable},
        )

    return DoctorCheck(
        id="uv",
        label="uv",
        status=CheckStatus.PASS,
        detail=probe.output or "uv is available",
        blocking=False,
        metadata={"executable": probe.executable, "version": probe.output},
    )


def check_docker_cli() -> DoctorCheck:
    """Find docker executable."""
    probe = _probe(["docker", "--version"], timeout=VERSION_TIMEOUT_SECONDS)

    if not probe.found:
        return DoctorCheck(
            id="docker_cli",
            label="Docker CLI",
            status=CheckStatus.WARN,
            detail=(
                "docker was not found on PATH; running an evaluated subject "
                "will need it"
            ),
            blocking=False,
            metadata={},
        )

    if not probe.succeeded:
        return DoctorCheck(
            id="docker_cli",
            label="Docker CLI",
            status=CheckStatus.WARN,
            detail=_probe_failure_detail("docker", probe),
            blocking=False,
            metadata={"executable": probe.executable},
        )

    return DoctorCheck(
        id="docker_cli",
        label="Docker CLI",
        status=CheckStatus.PASS,
        detail=probe.output or "docker is available",
        blocking=False,
        metadata={"executable": probe.executable, "version": probe.output},
    )


def check_docker_daemon() -> DoctorCheck:
    """Check Docker server reachability."""
    if shutil.which("docker") is None:
        return DoctorCheck(
            id="docker_daemon",
            label="Docker daemon",
            status=CheckStatus.SKIP,
            detail="Skipped because the docker executable was not found",
            blocking=False,
            metadata={},
        )

    probe = _probe(
        ["docker", "version", "--format", "{{.Server.Os}}/{{.Server.Arch}}"],
        timeout=DAEMON_TIMEOUT_SECONDS,
    )

    if not probe.succeeded or not probe.output:
        return DoctorCheck(
            id="docker_daemon",
            label="Docker daemon",
            status=CheckStatus.WARN,
            detail=_probe_failure_detail("the Docker daemon", probe),
            blocking=False,
            metadata={},
        )

    return DoctorCheck(
        id="docker_daemon",
        label="Docker daemon",
        status=CheckStatus.PASS,
        detail=f"reachable, serving {probe.output}",
        blocking=False,
        metadata={"docker_platform": probe.output},
    )


def check_hermes_cli() -> DoctorCheck:
    """Find Hermes and report version; warning only."""
    probe = _probe(["hermes", "--version"], timeout=VERSION_TIMEOUT_SECONDS)

    if not probe.found:
        return DoctorCheck(
            id="hermes",
            label="Hermes",
            status=CheckStatus.WARN,
            detail=(
                "hermes was not found on PATH; Techtree does not need it, and "
                "the host-agent integration is not part of this build"
            ),
            blocking=False,
            metadata={},
        )

    if not probe.succeeded:
        return DoctorCheck(
            id="hermes",
            label="Hermes",
            status=CheckStatus.WARN,
            detail=_probe_failure_detail("hermes", probe),
            blocking=False,
            metadata={"executable": probe.executable},
        )

    return DoctorCheck(
        id="hermes",
        label="Hermes",
        status=CheckStatus.PASS,
        detail=probe.output or "hermes is available",
        blocking=False,
        metadata={"executable": probe.executable, "version": probe.output},
    )


def check_active_engine(paths: TechtreePaths, settings: Settings) -> DoctorCheck:
    """Report whether active engine is installed and verified.

    Verification belongs to the managed engine subsystem, which this build does
    not contain. Doctor therefore reports what the filesystem can prove — the
    active pointer and whether anything is installed under it — and says
    plainly that verified is not yet a state it can observe.
    """
    digest = settings.active_engine_digest

    if digest is None:
        return DoctorCheck(
            id="active_engine",
            label="Active engine",
            status=CheckStatus.WARN,
            detail="No managed evaluation engine is active yet",
            blocking=False,
            metadata={"engine_status": EngineCompatibilityStatus.UNKNOWN.value},
        )

    directory = paths.engine_dir(digest)
    if not directory.is_dir():
        return DoctorCheck(
            id="active_engine",
            label="Active engine",
            status=CheckStatus.WARN,
            detail=(
                f"engine {digest} is recorded as active but is not installed "
                f"under {paths.engines_dir}"
            ),
            blocking=False,
            metadata={
                "engine_status": EngineCompatibilityStatus.NOT_INSTALLED.value,
                "engine_digest": digest,
            },
        )

    return DoctorCheck(
        id="active_engine",
        label="Active engine",
        status=CheckStatus.WARN,
        detail=(
            f"engine {digest} is installed; verifying it needs the managed "
            "engine subsystem, which this build does not contain"
        ),
        blocking=False,
        metadata={
            "engine_status": EngineCompatibilityStatus.INSTALLED_UNVERIFIED.value,
            "engine_digest": digest,
        },
    )


def _probe_failure_detail(subject: str, probe: _Probe) -> str:
    """Describe a tool that exists but did not answer."""
    if probe.timed_out:
        return f"{subject} did not answer within the timeout"
    if probe.output:
        return f"{subject} is present but reported: {probe.output}"
    return f"{subject} is present but did not answer"
