"""One function per thing that can be wrong with a host. Spec section 13.1.

Each check answers a single question and returns a :class:`~techtree.models.
cli.DoctorCheck` whether the answer is good or bad. No check raises: a Doctor
that stops at the first problem tells you about one problem, and the point of
Doctor is to tell you about all of them at once.

``blocking`` is a claim about *this* moment, not about the tool in general.
Python and a usable Techtree home block everything, so a failure there blocks.
uv blocks engine setup and nothing else, so an ordinary Doctor reports it as a
warning and says what it will block. Docker is a warning before the subject
work package exists.

Two checks here are about the host agent rather than about Techtree, and
neither is ever a fault. Hermes is where a person's agent drives Techtree from,
and the Techtree plugin is what puts Techtree's commands in front of that
agent; a machine with neither still runs every command in this program. So
both are observations with a next step attached, and the one thing they must
never do is turn a ready host into an unready one.

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

import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Final

from techtree.engines.registry import EngineRegistry
from techtree.errors import PrerequisiteError
from techtree.models.base import JsonValue
from techtree.models.catalog import EngineCompatibilityStatus
from techtree.models.cli import CheckStatus, DoctorCheck
from techtree.models.engine import normalize_host_platform
from techtree.paths import TechtreePaths
from techtree.settings import Settings

__all__ = [
    "DAEMON_TIMEOUT_SECONDS",
    "START_PAGE_URL",
    "SUPPORTED_PYTHON",
    "TECHTREE_PLUGIN_NAME",
    "VERSION_TIMEOUT_SECONDS",
    "check_active_engine",
    "check_docker_cli",
    "check_docker_daemon",
    "check_hermes_cli",
    "check_hermes_plugin",
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

#: The name the Techtree plugin registers with Hermes, and what Doctor looks
#: for in a plugin listing.
TECHTREE_PLUGIN_NAME: Final = "techtree"

#: The word Hermes writes beside a plugin it will actually load.
_ENABLED: Final = "enabled"

#: The two words Hermes writes beside a plugin it will not load: one nobody has
#: turned on, and one somebody turned off. Techtree's answer is the same for
#: both, because from where a person sits they are the same situation.
_NOT_ENABLED: Final[frozenset[str]] = frozenset({"not enabled", "disabled"})

#: Decision 0024 section 4: the pinned installation guide for this release.
#:
#: Doctor points at it instead of printing the plugin's install command, and
#: the reason is an ordering fact rather than a shortcut. Decision 0026 makes
#: the release contract a document that is authored first and describes only
#: what is knowable at that moment; the plugin then embeds a byte-identical
#: copy of that contract, and the website's release document names the commit
#: the plugin ended up at. A commit that comes into existence two steps after
#: the contract cannot be a field of the contract, so this program has no way
#: to know it — and a coordinate invented here would be worse than an address
#: that is always current.
START_PAGE_URL: Final = "https://techtree.sh/start"


@dataclass(frozen=True)
class _Probe:
    """What running one external tool told us.

    ``output`` is the one line a version probe is after. ``stdout`` is
    everything the tool wrote, which is what a machine-readable answer needs.
    """

    executable: str | None
    exit_code: int | None
    output: str
    stdout: str
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
        return _Probe(
            executable=None, exit_code=None, output="", stdout="", timed_out=False
        )

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
        return _Probe(
            executable=executable,
            exit_code=None,
            output="",
            stdout="",
            timed_out=True,
        )
    except OSError as error:
        return _Probe(
            executable=executable,
            exit_code=None,
            output=str(error.strerror or error),
            stdout="",
            timed_out=False,
        )

    return _Probe(
        executable=executable,
        exit_code=completed.returncode,
        output=_first_line(completed.stdout) or _first_line(completed.stderr),
        stdout=completed.stdout,
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
                "hermes was not found on PATH. Techtree runs inside Hermes, an "
                "open-source agent made by Nous Research; the CLI also works "
                "on its own. The pinned installation guide for this release is "
                f"{START_PAGE_URL}"
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


def check_hermes_plugin() -> DoctorCheck:
    """Say whether the Techtree plugin is installed and on for the Hermes on PATH.

    Never blocking, and never a failure. A host without the plugin is a
    perfectly good host: the CLI does its whole job on its own, and the plugin
    is what lets an agent drive it. So this is the same kind of observation
    ``check_active_engine`` makes about an engine that is not active yet — a
    next step, written as one.

    Installed and switched on are two questions, and a plugin can be the first
    without being the second. Answering only the first would tell somebody in
    that state that everything is fine while their agent still has no Techtree
    commands, so both are answered and the second carries the command that
    changes it.

    The answer is only as good as what Hermes will say. Plugins are held per
    profile as well as per user, so a listing describes the Hermes this
    command resolves to and not necessarily another profile's. And a Hermes
    that does not answer with a listing this build can read is reported as
    unknown rather than guessed at: an unfounded "not installed" would send
    someone to reinstall software they already have, and an unfounded "not
    switched on" would send them to turn on what is already running.
    """
    if shutil.which("hermes") is None:
        return DoctorCheck(
            id="hermes_plugin",
            label="Techtree plugin",
            status=CheckStatus.SKIP,
            detail="Skipped because the hermes executable was not found",
            blocking=False,
            metadata={},
        )

    probe = _probe(
        ["hermes", "plugins", "list", "--json"], timeout=VERSION_TIMEOUT_SECONDS
    )
    listing = _plugin_states(probe)

    if listing is None:
        return DoctorCheck(
            id="hermes_plugin",
            label="Techtree plugin",
            status=CheckStatus.SKIP,
            detail=(
                "Skipped because this Hermes did not return a plugin list this "
                "build can read"
            ),
            blocking=False,
            metadata={"timed_out": probe.timed_out, "exit_code": probe.exit_code},
        )

    if TECHTREE_PLUGIN_NAME not in listing:
        return DoctorCheck(
            id="hermes_plugin",
            label="Techtree plugin",
            status=CheckStatus.WARN,
            detail=(
                "The Techtree plugin is not installed for this Hermes. The CLI "
                "works without it, and installing it is what lets your agent "
                "drive Techtree for you. The pinned installation guide for "
                f"this release is {START_PAGE_URL}"
            ),
            blocking=False,
            metadata={"plugin_name": TECHTREE_PLUGIN_NAME, "installed": False},
        )

    state = listing[TECHTREE_PLUGIN_NAME]

    if state == _ENABLED:
        return DoctorCheck(
            id="hermes_plugin",
            label="Techtree plugin",
            status=CheckStatus.PASS,
            detail="The Techtree plugin is installed and switched on for this Hermes",
            blocking=False,
            metadata={
                "plugin_name": TECHTREE_PLUGIN_NAME,
                "installed": True,
                "enabled": True,
            },
        )

    if state in _NOT_ENABLED:
        return DoctorCheck(
            id="hermes_plugin",
            label="Techtree plugin",
            status=CheckStatus.WARN,
            detail=(
                "The Techtree plugin is installed for this Hermes but is not "
                "switched on, so your agent cannot see Techtree's commands yet. "
                "The CLI works either way. Switch it on with: hermes plugins "
                f"enable {TECHTREE_PLUGIN_NAME}"
            ),
            blocking=False,
            metadata={
                "plugin_name": TECHTREE_PLUGIN_NAME,
                "installed": True,
                "enabled": False,
            },
        )

    return DoctorCheck(
        id="hermes_plugin",
        label="Techtree plugin",
        status=CheckStatus.SKIP,
        detail=(
            "This Hermes lists the Techtree plugin but described its state in a "
            "word this build does not know, so whether it is switched on could "
            "not be established"
        ),
        blocking=False,
        metadata={"plugin_name": TECHTREE_PLUGIN_NAME, "installed": True},
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

    engine_status = EngineRegistry(paths, settings).status(digest)
    if engine_status.verified:
        return DoctorCheck(
            id="active_engine",
            label="Active engine",
            status=CheckStatus.PASS,
            detail=f"engine {digest} is installed and verified",
            blocking=False,
            metadata={
                "engine_status": EngineCompatibilityStatus.VERIFIED.value,
                "engine_digest": digest,
            },
        )

    return DoctorCheck(
        id="active_engine",
        label="Active engine",
        status=CheckStatus.WARN,
        detail=(
            f"engine {digest} is installed but not verified; "
            "run techtree setup to verify and activate it"
        ),
        blocking=False,
        metadata={
            "engine_status": EngineCompatibilityStatus.INSTALLED_UNVERIFIED.value,
            "engine_digest": digest,
        },
    )


def _plugin_states(probe: _Probe) -> dict[str, str | None] | None:
    """Map each listed plugin to the word beside it, or None if there is no listing.

    None for the whole listing is the honest answer to every way this can go
    wrong — a Hermes too old to know the flag, one that timed out, one that
    answered with something other than the documented array of plugin objects.
    Doctor says it does not know rather than reporting an absence it did not
    observe.

    A named plugin whose word is missing or is not text maps to None on its
    own. Dropping such an entry would be worse than keeping it: the plugin was
    listed, so reporting it as absent would be an absence nobody observed.
    """
    if not probe.succeeded:
        return None
    try:
        listing = json.loads(probe.stdout)
    except ValueError:
        return None
    if not isinstance(listing, list):
        return None
    states = {
        entry["name"]: entry["status"] if isinstance(entry.get("status"), str) else None
        for entry in listing
        if isinstance(entry, dict) and isinstance(entry.get("name"), str)
    }
    if listing and not states:
        # A listing of somethings, none of which is a named plugin, is a shape
        # this build does not understand. Reading it as "no plugins" would turn
        # an unread answer into a claim about the host.
        return None
    return states


def _probe_failure_detail(subject: str, probe: _Probe) -> str:
    """Describe a tool that exists but did not answer."""
    if probe.timed_out:
        return f"{subject} did not answer within the timeout"
    if probe.output:
        return f"{subject} is present but reported: {probe.output}"
    return f"{subject} is present but did not answer"
